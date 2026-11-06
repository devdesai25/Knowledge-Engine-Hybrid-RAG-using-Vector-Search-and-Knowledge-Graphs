import logging
import asyncio
import uuid 
from uuid import UUID
from time import perf_counter

import magic
from fastapi import UploadFile, Request
from sqlalchemy import delete
from neo4j.exceptions import ServiceUnavailable, SessionExpired

from backend.app.core.exceptions.exceptions import (
    UnsupportedMimeTypeError,
    ExtractionError,
    EmbeddingError,
    UpsertError,
    GenerationError,
)
from backend.app.extractor.registry import EXTRACTOR_REGISTRY
from backend.app.chunker.docling import DoclingChunker
from backend.app.embedder.embedding import generate_embedding
from backend.app.database.qdrant import upsert, delete_point
from backend.app.llm.client_er import llm_extraction
from backend.app.database.neo4j import neo4j_client
from backend.app.database.supabase import AsyncSessionLocal
from backend.app.models.bm25_text_search import Document
from backend.app.models.chunks import Chunk

logger = logging.getLogger(__name__)

MIME_SNIFF_SIZE = 2048

# Module-level semaphore to serialize CPU-bound Docling document extractions
_DOCLING_SEMAPHORE = asyncio.Semaphore(1)

async def process_single_file(request: Request, file: UploadFile, user_id: UUID) -> dict:
    """
    Processes a single uploaded document in two decoupled phases:
      Phase 1 (Compute): Docling conversion (serialized by semaphore), chunking,
                         LLM graph extraction, and embeddings. No DB sessions held.
      Phase 2 (Write): Fast, short transactional writes to Qdrant, Neo4j, and Postgres.
                       On any failure, rolls back Qdrant, Neo4j, and Postgres for doc_id.
    """
    start_total = perf_counter()
    model = request.app.state.embedder
    file_name = file.filename
    doc_id = uuid.uuid4()

    read_time = 0.0
    extract_time = 0.0
    chunk_time = 0.0
    graph_gen_time = 0.0
    embed_time = 0.0
    qdrant_time = 0.0
    neo4j_time = 0.0
    postgres_time = 0.0
    qdrant_batches = 0
    num_pg_batches = 0

    try:
        # -------------------- PHASE 1: COMPUTE (NO DB SESSIONS OPEN) --------------------
        # Step 1: File read & MIME check
        t_read = perf_counter()
        data_chunk = await file.read(MIME_SNIFF_SIZE)
        mime_type = magic.from_buffer(data_chunk, mime=True)
        await file.seek(0)

        extractor = EXTRACTOR_REGISTRY.get(mime_type)
        if extractor is None:
            raise UnsupportedMimeTypeError(f"Unsupported MIME TYPE: {mime_type}")
        read_time = perf_counter() - t_read
        logger.info("[TIMING] %s | File read: %.3fs", file_name, read_time)

        # Step 2: Docling extraction (Serialized via semaphore to eliminate CPU contention)
        t_extract = perf_counter()
        async with _DOCLING_SEMAPHORE:
            document = await extractor.extract(file)
        extract_time = perf_counter() - t_extract
        logger.info("[TIMING] %s | Docling extraction: %.3fs", file_name, extract_time)

        # Step 3: Chunking (Offloaded to worker thread)
        t_chunk = perf_counter()
        chunks = await asyncio.to_thread(DoclingChunker.chunk_docment, document, file_name, user_id, doc_id)
        if not chunks:
            raise ExtractionError("Document contains no extractable text.")
        chunk_time = perf_counter() - t_chunk
        logger.info("[TIMING] %s | Chunking: %.3fs", file_name, chunk_time)

        # Extract text from chunks
        text = [chunk["text"] for chunk in chunks]

        # Step 4: Neo4j graph extraction (Non-blocking async LLM with chunk batching)
        t_graph = perf_counter()
        graph = await llm_extraction.generate_structure(text)
        graph_gen_time = perf_counter() - t_graph
        logger.info("[TIMING] %s | Neo4j graph extraction: %.3fs", file_name, graph_gen_time)

        # Step 5: Embedding generation (Offloaded to worker thread to prevent event loop blocking)
        t_embed = perf_counter()
        embeddings = await asyncio.to_thread(generate_embedding, text, model)
        embed_time = perf_counter() - t_embed
        logger.info("[TIMING] %s | Embedding generation: %.3fs", file_name, embed_time)

        # -------------------- PHASE 2: WRITE (SHORT, FRESH SESSIONS, RETRIED) --------------------
        try:
            # Step 6: Qdrant upsert (Batched in 128s with deterministic UUID5 point IDs and 3 retries)
            t_qdrant = perf_counter()
            qdrant_res = await upsert(embeddings, chunks, user_id=user_id, doc_id=doc_id)
            qdrant_batches = qdrant_res.get("batches", (len(chunks) + 127) // 128)
            qdrant_time = perf_counter() - t_qdrant
            logger.info(
                "[TIMING] %s | Qdrant upsert (%d points, %d batches): %.3fs",
                file_name, len(chunks), qdrant_batches, qdrant_time
            )

            # Step 7: Neo4j graph insert (3-attempt retry with exponential backoff on transient drops)
            t_neo4j = perf_counter()
            neo4j_max_retries = 3
            for attempt in range(neo4j_max_retries):
                try:
                    await neo4j_client.insert_graph(
                        graph=graph,
                        file_name=file_name,
                        user_id=user_id,
                        doc_id=doc_id,
                    )
                    break
                except (ServiceUnavailable, SessionExpired) as e:
                    if attempt < neo4j_max_retries - 1:
                        backoff = 2.0 ** attempt  # 1s, 2s
                        logger.warning(
                            "Neo4j insert_graph encountered %s (%s). Retrying in %.1fs (attempt %d/%d)...",
                            type(e).__name__, e, backoff, attempt + 1, neo4j_max_retries
                        )
                        await asyncio.sleep(backoff)
                    else:
                        logger.error(
                            "Neo4j insert_graph failed after %d attempts: %s: %s",
                            neo4j_max_retries, type(e).__name__, e
                        )
                        raise
            neo4j_time = perf_counter() - t_neo4j
            logger.info(
                "[TIMING] %s | Neo4j graph insert (%d entities, %d relationships): %.3fs",
                file_name, len(graph.entities), len(graph.relationships), neo4j_time
            )

            # Step 8: Postgres insert (Fresh session with session.begin(), idempotent, batched in 200s)
            t_pg = perf_counter()
            total_chunks = len(chunks)
            PG_BATCH_SIZE = 200
            num_pg_batches = (total_chunks + PG_BATCH_SIZE - 1) // PG_BATCH_SIZE if total_chunks > 0 else 0

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Idempotency: delete any existing chunks & document for doc_id + user_id
                    await session.execute(
                        delete(Chunk).where(Chunk.doc_id == doc_id, Chunk.user_id == user_id)
                    )
                    await session.execute(
                        delete(Document).where(Document.doc_id == doc_id, Document.user_id == user_id)
                    )

                    # Insert parent Document row first and flush to satisfy foreign keys
                    db_doc = Document(
                        doc_id=doc_id,
                        user_id=user_id,
                        doc_name=file_name,
                    )
                    session.add(db_doc)
                    await session.flush()

                    # Insert Chunk rows in batches of 200
                    for i in range(0, total_chunks, PG_BATCH_SIZE):
                        chunk_slice = chunks[i:i + PG_BATCH_SIZE]
                        batch_objects = [
                            Chunk(
                                chunk_id=uuid.UUID(str(chunk["meta"]["chunk_id"])),
                                doc_id=doc_id,
                                user_id=user_id,
                                content=chunk["text"],
                                chunk_index=i + offset,
                                page_no=chunk["meta"]["page_no"],
                                doc_name=file_name,
                                heading=chunk["meta"].get("headings") or "",
                            )
                            for offset, chunk in enumerate(chunk_slice)
                        ]
                        session.add_all(batch_objects)
                        await session.flush()

            postgres_time = perf_counter() - t_pg
            logger.info(
                "[TIMING] %s | Postgres insert (1 doc, %d chunks, %d batches): %.3fs",
                file_name, total_chunks, num_pg_batches, postgres_time
            )

        except Exception as write_err:
            logger.error(
                "Write phase failed for %s (%s: %s). Rolling back all storage layers...",
                file_name, type(write_err).__name__, write_err
            )
            t_rollback = perf_counter()
            # 1. Clean up Qdrant by filter (doc_id + user_id payload)
            try:
                await delete_point(doc_id=doc_id, user_id=user_id)
            except Exception as q_err:
                logger.warning("Rollback Qdrant failed for %s (%s: %s)", file_name, type(q_err).__name__, q_err)

            # 2. Clean up Neo4j graph for doc_id + user_id
            try:
                await neo4j_client.delete_graph(doc_id=doc_id, user_id=user_id)
            except Exception as n_err:
                logger.warning("Rollback Neo4j failed for %s (%s: %s)", file_name, type(n_err).__name__, n_err)

            # 3. Clean up Postgres rows for doc_id + user_id in fresh session
            try:
                async with AsyncSessionLocal() as rb_session:
                    async with rb_session.begin():
                        await rb_session.execute(
                            delete(Chunk).where(Chunk.doc_id == doc_id, Chunk.user_id == user_id)
                        )
                        await rb_session.execute(
                            delete(Document).where(Document.doc_id == doc_id, Document.user_id == user_id)
                        )
            except Exception as p_err:
                logger.warning("Rollback Postgres failed for %s (%s: %s)", file_name, type(p_err).__name__, p_err)

            rollback_time = perf_counter() - t_rollback
            logger.info("[TIMING] %s | Rollback/cleanup: %.3fs", file_name, rollback_time)
            raise

        total_elapsed = perf_counter() - start_total
        logger.info(
            "\n"
            "==================== UPLOAD TIMING BREAKDOWN: %s ====================\n"
            "  1. File read            : %.3fs\n"
            "  2. Docling extraction   : %.3fs\n"
            "  3. Chunking             : %.3fs\n"
            "  4. Neo4j graph extraction : %.3fs\n"
            "  5. Embedding generation : %.3fs\n"
            "  6. Qdrant upsert (%d pts, %d bts): %.3fs\n"
            "  7. Neo4j graph insert (%d ent, %d rel): %.3fs\n"
            "  8. Postgres insert (1 doc, %d chk, %d bts): %.3fs\n"
            "--------------------------------------------------------------------\n"
            "  TOTAL ELAPSED TIME      : %.3fs\n"
            "====================================================================",
            file_name,
            read_time,
            extract_time,
            chunk_time,
            graph_gen_time,
            embed_time,
            len(chunks),
            qdrant_batches,
            qdrant_time,
            len(graph.entities),
            len(graph.relationships),
            neo4j_time,
            len(chunks),
            num_pg_batches,
            postgres_time,
            total_elapsed,
        )

        logger.info(
            "Processed %s | chunks %d | time: %.2fs",
            file.filename,
            len(chunks),
            total_elapsed,
        )

        return {
            "filename": file.filename,
            "status": "success",
            "chunks": len(chunks),
        }

    except (
        UnsupportedMimeTypeError,
        ExtractionError,
        EmbeddingError,
        UpsertError,
        GenerationError,
    ) as e:
        logger.exception(
            "Processing failed for %s (%s: %s)",
            file.filename, type(e).__name__, e
        )
        return {
            "filename": file.filename,
            "status": "failed",
            "error": f"{type(e).__name__}: {e}",
        }

    except Exception as e:
        logger.exception(
            "Unexpected error while processing %s (%s: %s)",
            file.filename, type(e).__name__, e
        )
        return {
            "filename": file.filename,
            "status": "failed",
            "error": f"{type(e).__name__}: {e}",
        }


async def upload_service(request: Request, files: list[UploadFile], user_id: UUID) -> dict:
    start_total = perf_counter()

    results = await asyncio.gather(
        *(process_single_file(request, file, user_id) for file in files)
    )

    uploaded = sum(result["status"] == "success" for result in results)
    failed = len(results) - uploaded
    total_elapsed = perf_counter() - start_total

    if len(files) > 1:
        logger.info(
            "\n"
            "==================== BATCH UPLOAD SUMMARY ====================\n"
            "  Files processed : %d\n"
            "  Succeeded       : %d\n"
            "  Failed          : %d\n"
            "--------------------------------------------------------------\n"
            "  TOTAL TIME      : %.3fs\n"
            "==============================================================",
            len(files),
            uploaded,
            failed,
            total_elapsed,
        )

    return {
        "uploaded": uploaded,
        "failed": failed,
        "details": results,
    }
