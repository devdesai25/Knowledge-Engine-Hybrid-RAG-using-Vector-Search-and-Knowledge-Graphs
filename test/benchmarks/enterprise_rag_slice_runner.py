import asyncio
import io
import json
import logging
import os
import sys
import uuid
import zipfile
from pathlib import Path
from uuid import UUID

import requests
from sentence_transformers import SentenceTransformer

# Ensure benchmarks dir and repo root are on sys.path
BENCHMARK_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BENCHMARK_DIR.parent.parent
if str(BENCHMARK_DIR) not in sys.path:
    sys.path.insert(0, str(BENCHMARK_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.settings import setting
from backend.app.database.supabase import AsyncSessionLocal
from backend.app.models.user import User
from backend.app.models.bm25_text_search import Document
from backend.app.models.chunks import Chunk
from backend.app.database.qdrant import upsert as qdrant_upsert
from backend.app.database.neo4j import neo4j_client
from backend.app.llm.client_er import llm_extraction
from backend.app.embedder.embedding import generate_embedding
from benchmark_engine import BenchmarkEngine

logger = logging.getLogger("enterprise_slice")
logging.basicConfig(level=logging.INFO)

EVAL_USER_ID = UUID("00000000-0000-0000-0000-000000000001")

Q_URL = "https://github.com/onyx-dot-app/EnterpriseRAG-Bench/releases/download/v1.0.0/questions.jsonl"
CONFLUENCE_SLICE_URL = "https://github.com/onyx-dot-app/EnterpriseRAG-Bench/releases/download/v1.0.0/confluence_slice_0002.zip"
JIRA_SLICE_URL = "https://github.com/onyx-dot-app/EnterpriseRAG-Bench/releases/download/v1.0.0/jira_slice_0002.zip"


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += max(1, chunk_size - overlap)
    return chunks or [text]


async def prepare_eval_user(session):
    user = await session.get(User, EVAL_USER_ID)
    if not user:
        user = User(
            id=EVAL_USER_ID,
            email="benchmark_eval@example.com",
            password_hash="benchmark_dummy_hash",
        )
        session.add(user)
        await session.commit()
        logger.info("Created evaluation user: %s", EVAL_USER_ID)


async def ingest_enterprise_slice(max_docs: int = 10):
    logger.info("Downloading official EnterpriseRAG-Bench questions...")
    q_resp = requests.get(Q_URL, timeout=30)
    questions = [json.loads(line) for line in q_resp.text.splitlines() if line.strip()]
    logger.info("Loaded %d benchmark questions.", len(questions))

    logger.info("Downloading enterprise slice archives...")
    z_confluence = zipfile.ZipFile(io.BytesIO(requests.get(CONFLUENCE_SLICE_URL, timeout=40).content))
    z_jira = zipfile.ZipFile(io.BytesIO(requests.get(JIRA_SLICE_URL, timeout=40).content))

    corpus_docs = {}
    for z in [z_confluence, z_jira]:
        for name in z.namelist():
            base = name.split("/")[-1]
            if "__" in base and base.endswith(".txt"):
                parts = base.split("__", 1)
                doc_id = parts[0]
                title = parts[1].replace(".txt", "").replace("-", " ")
                content = z.read(name).decode("utf-8", errors="ignore")
                corpus_docs[doc_id] = {"doc_id": doc_id, "title": title, "content": content}

    logger.info("Loaded %d documents from slices.", len(corpus_docs))

    # Match questions
    matched_questions = []
    for q in questions:
        expected = q.get("expected_doc_ids", [])
        if any(d in corpus_docs for d in expected):
            matched_questions.append(q)

    logger.info("Found %d questions with ground truth in this slice.", len(matched_questions))

    # Select target questions & documents
    selected_questions = matched_questions[:5]
    needed_doc_ids = set()
    for q in selected_questions:
        needed_doc_ids.update(q.get("expected_doc_ids", []))

    selected_docs = [corpus_docs[did] for did in needed_doc_ids if did in corpus_docs]
    # Add a few distractors
    for did, d_data in corpus_docs.items():
        if did not in needed_doc_ids and len(selected_docs) < max_docs:
            selected_docs.append(d_data)

    logger.info("Selected %d documents and %d questions for benchmark run.", len(selected_docs), len(selected_questions))

    out_q_path = "test/benchmarks/enterprise_rag_slice_questions.json"
    with open(out_q_path, "w", encoding="utf-8") as f:
        json.dump(selected_questions, f, indent=2)

    # Ingestion
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    async with AsyncSessionLocal() as db:
        await prepare_eval_user(db)

    for idx, d_item in enumerate(selected_docs, 1):
        doc_raw_id = d_item["doc_id"]
        doc_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, doc_raw_id)
        title = d_item["title"]
        content = d_item["content"]

        logger.info("[%d/%d] Ingesting enterprise doc %s: %s", idx, len(selected_docs), doc_raw_id, title[:40])
        chunks = chunk_text(content, chunk_size=400, overlap=50)

        # Neo4j Graph Insertion
        try:
            logger.info("  -> Extracting entities & relationships via LLM...")
            graph_struct = await llm_extraction.generate_structure(chunks[:2])
            await neo4j_client.insert_graph(
                graph=graph_struct,
                file_name=title,
                user_id=EVAL_USER_ID,
                doc_id=doc_uuid,
            )
            logger.info("  -> Neo4j: merged %d entities, %d rels", len(graph_struct.entities), len(graph_struct.relationships))
        except Exception as e:
            logger.warning("  -> Neo4j error: %s", e)

        # Qdrant Vector Upsert
        try:
            embeddings = generate_embedding(chunks, model)
            points = [
                {
                    "text": c,
                    "meta": {
                        "chunk_id": str(uuid.uuid4()),
                        "doc_id": str(doc_uuid),
                        "user_id": str(EVAL_USER_ID),
                        "file_name": title,
                        "page_no": 1,
                        "headings": title,
                    },
                }
                for c in chunks
            ]
            await qdrant_upsert(embeddings, points, user_id=EVAL_USER_ID, doc_id=doc_uuid)
            logger.info("  -> Qdrant: upserted %d vectors", len(chunks))
        except Exception as e:
            logger.warning("  -> Qdrant error: %s", e)

        # Postgres BM25 Insertion
        try:
            async with AsyncSessionLocal() as db:
                pg_doc = Document(doc_id=doc_uuid, user_id=EVAL_USER_ID, doc_name=title)
                db.add(pg_doc)
                await db.commit()

                pg_chunks = [
                    Chunk(
                        chunk_id=uuid.uuid4(),
                        doc_id=doc_uuid,
                        user_id=EVAL_USER_ID,
                        content=c,
                        chunk_index=c_idx,
                        page_no=1,
                        doc_name=title,
                        heading=title,
                    )
                    for c_idx, c in enumerate(chunks)
                ]
                db.add_all(pg_chunks)
                await db.commit()
            logger.info("  -> Postgres: saved doc and %d chunks", len(pg_chunks))
        except Exception as e:
            logger.warning("  -> Postgres error: %s", e)

    return out_q_path, str(EVAL_USER_ID)


async def main():
    q_file = "test/benchmarks/enterprise_rag_slice_questions.json"
    eval_uid = str(EVAL_USER_ID)

    # Check if already ingested
    already_ingested = False
    if os.path.exists(q_file):
        async with AsyncSessionLocal() as s:
            from sqlalchemy import select, func
            count = await s.scalar(select(func.count(Chunk.chunk_id)).where(Chunk.user_id == EVAL_USER_ID))
            if count and count > 0:
                already_ingested = True
                logger.info("Found %d already ingested chunks for eval user. Skipping re-ingestion.", count)

    if not already_ingested:
        q_file, eval_uid = await ingest_enterprise_slice(max_docs=6)

    print("\n======================================================================")
    print("   RUNNING ENTERPRISE RAG-BENCH ABLATION ON INGESTED ENTERPRISE DATA")
    print("======================================================================\n")

    engine = BenchmarkEngine(UUID(eval_uid))
    with open(q_file, "r", encoding="utf-8") as f:
        questions = json.load(f)

    # Convert expected_doc_ids to UUID5 so recall checking matches the database doc_ids
    for q in questions:
        q["expected_doc_ids"] = [
            str(uuid.uuid5(uuid.NAMESPACE_DNS, d)) for d in q.get("expected_doc_ids", [])
        ]

    results = []
    for idx, q in enumerate(questions, 1):
        print(f"[{idx}/{len(questions)}] Evaluating: {q['question_id']} ({q['question_type']})...")
        res = await engine.run_question(q)
        results.append(res)
        for m_key, m in res.modes.items():
            print(f"   * {m.mode:<16} | Recall: {m.doc_recall:.2f} | Fact Score: {m.correctness_score:.2f} | Latency: {m.latency_sec}s")

    print("\n" + "=" * 70)
    print("      ENTERPRISE RAG-BENCH TARGETED SLICE EVALUATION REPORT")
    print("=" * 70)
    print(f"{'Mode':<18} | {'Avg Recall@5':<14} | {'Fact Score':<12} | {'Avg Latency':<12}")
    print("-" * 70)
    modes = ["vector_only", "fts_only", "hybrid_rrf", "hybrid_graph"]
    summary_data = {}
    for m_key in modes:
        mode_name = results[0].modes[m_key].mode
        avg_rec = sum(r.modes[m_key].doc_recall for r in results) / len(results)
        avg_score = sum(r.modes[m_key].correctness_score for r in results) / len(results)
        avg_lat = sum(r.modes[m_key].latency_sec for r in results) / len(results)
        summary_data[mode_name] = {
            "avg_recall": round(avg_rec, 3),
            "avg_fact_score": round(avg_score, 3),
            "avg_latency_sec": round(avg_lat, 2),
        }
        print(f"{mode_name:<18} | {avg_rec * 100:6.1f}%       | {avg_score * 100:6.1f}%     | {avg_lat:6.2f}s")
    print("=" * 70)

    out_results_path = "test/benchmarks/enterprise_rag_slice_results.json"
    with open(out_results_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)
    print(f"\nSaved EnterpriseRAG-Bench slice results to: {out_results_path}")
    await neo4j_client.close()


if __name__ == "__main__":
    asyncio.run(main())
