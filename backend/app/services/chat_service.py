import asyncio
import logging
import re
from time import perf_counter
from uuid import UUID
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from fastapi import Request
from qdrant_client import models
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.settings import setting
from backend.app.embedder.embedding import generate_embedding
from backend.app.database.qdrant import client
from backend.app.schema.chat import ChatRequest
from backend.app.llm.client import LLMClient
from backend.app.graph.schema import GRAPH_SCHEMA_PROMPT
from backend.app.graph.multi_hop_service import MultiHopGraphService
from backend.app.models.chunks import Chunk

RRF_K = 60

logger = logging.getLogger(__name__)

async def vector_search(query, user_id: UUID, model):
    t0 = perf_counter()
    embed_start = perf_counter()
    query_embed = generate_embedding(query.query, model)
    embed_time = perf_counter() - embed_start
    print("\nQUERY EMBEDDING:  ", query_embed)
    qdrant_start = perf_counter()
    response = await client.query_points(
        "rag-kg",
        query=query_embed,
        query_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="meta.user_id", match=models.MatchValue(value=str(user_id))
                )
            ]
        ),
        limit=25,
    )
    qdrant_time = perf_counter() - qdrant_start
    results = []

    for p in response.points:
        meta = p.payload.get("meta", {})
        results.append({
            "text": p.payload.get('text'),
            **meta,
            "vec_score": p.score
        })

    total_vec_time = perf_counter() - t0
    logger.info(
        "[TIMING] vector_search: %.3fs (embed: %.3fs, qdrant: %.3fs, points: %d)",
        total_vec_time,
        embed_time,
        qdrant_time,
        len(results),
    )
    return results

async def fts_search(query, user_id: UUID, db: AsyncSession):
    t0 = perf_counter()
    tsquery = func.websearch_to_tsquery("english", query.query)
    stmt = (
        select(
            Chunk,
            func.ts_rank_cd(Chunk.fts, tsquery).label("score")
        )
        .where(Chunk.fts.op("@@")(tsquery))
        .where(Chunk.user_id == user_id)
        .order_by(func.ts_rank_cd(Chunk.fts, tsquery).desc())
        .limit(50)
    )   

    db_start = perf_counter()
    result = await db.execute(stmt)
    rows = result.all()
    if not rows:
        # Fallback for natural language queries: if strict AND matched 0 rows,
        # extract keywords and match via OR ranking
        words = [w for w in re.findall(r'[a-zA-Z0-9]+', query.query) if len(w) > 2]
        if words:
            try:
                or_tsquery = func.to_tsquery("english", " | ".join(words))
                stmt_fallback = (
                    select(
                        Chunk,
                        func.ts_rank_cd(Chunk.fts, or_tsquery).label("score")
                    )
                    .where(Chunk.fts.op("@@")(or_tsquery))
                    .where(Chunk.user_id == user_id)
                    .order_by(func.ts_rank_cd(Chunk.fts, or_tsquery).desc())
                    .limit(50)
                )
                res_fallback = await db.execute(stmt_fallback)
                rows = res_fallback.all()
            except Exception as e:
                logger.debug("FTS fallback to_tsquery error: %s", e)
    db_time = perf_counter() - db_start

    results = []
    for r, fts_score in rows:
        d = {
            column.name: getattr(r, column.name)
            for column in Chunk.__table__.columns
        }
        d["chunk_id"] = str(d["chunk_id"])
        d["doc_id"] = str(d["doc_id"])
        d["user_id"] = str(d["user_id"])

        d["fts_score"] = float(fts_score)
        results.append(d)

    total_fts_time = perf_counter() - t0
    logger.info(
        "[TIMING] fts_search (Postgres): %.3fs (query_exec: %.3fs, rows: %d)",
        total_fts_time,
        db_time,
        len(results),
    )
    return results    

async def graph_search(
    query, 
    user_id: UUID, 
    context_doc_id: list[UUID] | None = None,
    max_hops: int = 2
) -> list[dict]:
    """
    Executes independent multi-hop Knowledge Graph search.
    Traverses entities and relational bridges without depending on vector/FTS candidate doc IDs.
    """
    query_text = query.query if hasattr(query, "query") else str(query)
    service = MultiHopGraphService()
    try:
        return await service.search(
            query_text=query_text,
            user_id=user_id,
            context_doc_id=context_doc_id,
            max_hops=max_hops,
        )
    except Exception as e:
        logger.warning("[Multi-Hop Graph Error]: %s. Continuing with empty graph context.", e)
        return []

def rrf_fuse(vec_results: list[dict], fts_results: list[dict], k: int = RRF_K):

    merged: dict[str, dict] = {}

    def upsert(item: dict, rank_key:str, rank:int)->None:
        cid = item["chunk_id"]
        entry = merged.get(cid)

        if entry is None:
            entry = {"vec_rank": None, "ts_rank": None}
            merged[cid] = entry

        for key,val in item.items():
            if key not in entry or entry[key] is None:
                entry[key] = val

        if entry[rank_key] is None:
            entry[rank_key] = rank

    for rank, item in enumerate(vec_results, start=1):
        upsert(item, "vec_rank", rank)

    for rank, item in enumerate(fts_results, start=1):
        upsert(item, "ts_rank", rank)
 
    for entry in merged.values():
        entry["rrf"] = sum(
            1.0 / (k + r) for r in (entry["vec_rank"], entry["ts_rank"]) if r is not None
        )
 
    return sorted(merged.values(), key=lambda e: e["rrf"], reverse=True)

def extract_doc_ids(rrf_result: list[dict], top_n: int = 10) -> list[str]:
    seen = set()
    doc_ids = []
    for entry in rrf_result[:top_n]:
        doc_id = entry.get("doc_id")
        if doc_id and doc_id not in seen:
            seen.add(doc_id)
            doc_ids.append(str(doc_id))
    return doc_ids

async def retrive(request: Request, query: ChatRequest, user_id: UUID, db: AsyncSession):
    start_total = perf_counter()
    model = request.app.state.embedder

    # Step 1: Execute Vector Search, FTS, and Independent Multi-Hop Graph Search in parallel
    t_parallel_start = perf_counter()
    vector_results, fts_results, graph_results = await asyncio.gather(
        vector_search(query, user_id, model),
        fts_search(query, user_id, db),
        graph_search(query, user_id),
    )
    parallel_time = perf_counter() - t_parallel_start

    # Step 2: RRF Fusing across Vector & FTS chunks
    t_rrf_start = perf_counter()
    rrf_result = rrf_fuse(vector_results, fts_results)
    rrf_time = perf_counter() - t_rrf_start

    # Step 3: Top fused chunks (defaults to top 10 from RRF, fallback to vector_results)
    top_chunks = rrf_result[:10] if rrf_result else vector_results[:10]

    # Step 4: Final LLM Answer Generation combining fused text chunks + multi-hop graph subgraphs
    t_llm_start = perf_counter()
    response = await LLMClient().generate(query.query, top_chunks, graph_results)
    llm_gen_time = perf_counter() - t_llm_start

    total_elapsed = perf_counter() - start_total
    logger.info(
        "\n"
        "==================== PARALLEL HYBRID + GRAPH RETRIEVAL TIMING ====================\n"
        "  1. Parallel Track (Vector + FTS + Multi-Hop KG) : %.3fs\n"
        "  2. RRF Fusion                                   : %.4fs\n"
        "  3. Final LLM Generation                         : %.3fs\n"
        "----------------------------------------------------------------------------------\n"
        "  TOTAL ELAPSED TIME                              : %.3fs\n"
        "==================================================================================",
        parallel_time,
        rrf_time,
        llm_gen_time,
        total_elapsed,
    )

    return response
