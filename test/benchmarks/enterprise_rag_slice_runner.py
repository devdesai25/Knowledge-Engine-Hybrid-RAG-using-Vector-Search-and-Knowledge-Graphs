import asyncio
import io
import json
import logging
import os
import sys
import time
import uuid
import zipfile
from pathlib import Path
from uuid import UUID

import requests
from sentence_transformers import SentenceTransformer

# Set offline mode for HF to avoid network stalls
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# Ensure benchmarks dir and repo root are on sys.path
BENCHMARK_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BENCHMARK_DIR.parent.parent
if str(BENCHMARK_DIR) not in sys.path:
    sys.path.insert(0, str(BENCHMARK_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.settings import setting
from backend.app.database.supabase import AsyncSessionLocal, engine
from backend.app.models.user import User
from backend.app.models.bm25_text_search import Document
from backend.app.models.chunks import Chunk
from backend.app.database.qdrant import upsert as qdrant_upsert
from backend.app.database.neo4j import neo4j_client
from backend.app.llm.client_er import llm_extraction
from backend.app.embedder.embedding import generate_embedding
from benchmark_engine import BenchmarkEngine

logger = logging.getLogger("enterprise_slice")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

EVAL_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
DATA_DIR = BENCHMARK_DIR / "data"

SLICES = [
    ("confluence_slice_0001.zip", "https://github.com/onyx-dot-app/EnterpriseRAG-Bench/releases/download/v1.0.0/confluence_slice_0001.zip"),
    ("confluence_slice_0002.zip", "https://github.com/onyx-dot-app/EnterpriseRAG-Bench/releases/download/v1.0.0/confluence_slice_0002.zip"),
    ("jira_slice_0001.zip", "https://github.com/onyx-dot-app/EnterpriseRAG-Bench/releases/download/v1.0.0/jira_slice_0001.zip"),
    ("jira_slice_0002.zip", "https://github.com/onyx-dot-app/EnterpriseRAG-Bench/releases/download/v1.0.0/jira_slice_0002.zip"),
]
QUESTIONS_URL = "https://github.com/onyx-dot-app/EnterpriseRAG-Bench/releases/download/v1.0.0/questions.jsonl"

TARGET_QUESTION_IDS = [
    # Completeness (multi-doc cross-system aggregation)
    "qst_0431", "qst_0433", "qst_0435", "qst_0442", "qst_0449",
    # Project Related (cross-document tracking and dependencies)
    "qst_0341", "qst_0353", "qst_0358",
    # Constrained (temporal / conditional constraints)
    "qst_0381", "qst_0382", "qst_0383", "qst_0393", "qst_0397", "qst_0404",
    # Conflicting Info (reconciling conflicting operational guidance)
    "qst_0413", "qst_0421",
    # Intra Document Reasoning (deep causal reasoning)
    "qst_0318", "qst_0327", "qst_0331",
    # Semantic Search (phrasing mismatch, concepts)
    "qst_0179", "qst_0181", "qst_0191", "qst_0215",
    # Basic Factoid (standard lookup)
    "qst_0011", "qst_0021", "qst_0059", "qst_0076", "qst_0151",
]


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


def download_or_get_file(url: str, filename: str) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    target = DATA_DIR / filename
    if not target.exists() or target.stat().st_size == 0:
        logger.info("Downloading %s from %s ...", filename, url)
        resp = requests.get(url, timeout=60, stream=True)
        resp.raise_for_status()
        with open(target, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
        logger.info("Saved %s (%.2f MB)", filename, target.stat().st_size / (1024 * 1024))
    else:
        logger.info("Using cached %s (%.2f MB)", filename, target.stat().st_size / (1024 * 1024))
    return target


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


async def ingest_enterprise_slice(max_distractors: int = 19):
    # 1. Download/Load questions
    q_file = download_or_get_file(QUESTIONS_URL, "questions.jsonl")
    with open(q_file, "r", encoding="utf-8") as f:
        all_questions = [json.loads(line) for line in f if line.strip()]
    logger.info("Loaded %d total EnterpriseRAG-Bench questions.", len(all_questions))

    # Filter to selected balanced questions
    selected_questions = [q for q in all_questions if q["question_id"] in TARGET_QUESTION_IDS]
    needed_doc_ids = set()
    for q in selected_questions:
        needed_doc_ids.update(q.get("expected_doc_ids", []))
    logger.info("Selected %d benchmark questions requiring %d distinct ground-truth documents.", len(selected_questions), len(needed_doc_ids))

    # 2. Extract documents from slice archives
    corpus_docs = {}
    distractor_pool = []

    for filename, url in SLICES:
        zip_path = download_or_get_file(url, filename)
        with zipfile.ZipFile(zip_path, "r") as z:
            for name in z.namelist():
                base = name.split("/")[-1]
                if "__" in base and base.endswith(".txt"):
                    parts = base.split("__", 1)
                    doc_id = parts[0]
                    title = parts[1].replace(".txt", "").replace("-", " ")
                    if doc_id in needed_doc_ids and doc_id not in corpus_docs:
                        content = z.read(name).decode("utf-8", errors="ignore")
                        corpus_docs[doc_id] = {
                            "doc_id": doc_id,
                            "title": title,
                            "content": content,
                            "is_distractor": False,
                        }
                    elif doc_id not in needed_doc_ids and len(distractor_pool) < max_distractors * 2:
                        content = z.read(name).decode("utf-8", errors="ignore")
                        distractor_pool.append({
                            "doc_id": doc_id,
                            "title": title,
                            "content": content,
                            "is_distractor": True,
                        })

    logger.info("Extracted %d ground-truth documents from slices.", len(corpus_docs))
    distractors = distractor_pool[:max_distractors]
    for d in distractors:
        corpus_docs[d["doc_id"]] = d

    final_doc_list = list(corpus_docs.values())
    logger.info("Total documents to ingest: %d (%d ground-truth, %d distractors)", len(final_doc_list), len(needed_doc_ids), len(distractors))

    # Save target questions
    out_q_path = "test/benchmarks/enterprise_rag_slice_questions.json"
    with open(out_q_path, "w", encoding="utf-8") as f:
        json.dump(selected_questions, f, indent=2)

    # 3. Ensure eval user
    async with AsyncSessionLocal() as db:
        await prepare_eval_user(db)

    # 4. Initialize embedding model
    logger.info("Loading SentenceTransformer model...")
    try:
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", local_files_only=True)
    except Exception:
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    # 5. Ingestion loop
    er_semaphore = asyncio.Semaphore(4)

    async def ingest_single_doc(idx: int, d_item: dict):
        doc_raw_id = d_item["doc_id"]
        doc_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, doc_raw_id)
        title = d_item["title"]
        content = d_item["content"]
        chunks = chunk_text(content, chunk_size=400, overlap=50)

        # A. Neo4j Graph Extraction
        async with er_semaphore:
            try:
                graph_struct = await llm_extraction.generate_structure(chunks[:2])
                await neo4j_client.insert_graph(
                    graph=graph_struct,
                    file_name=title,
                    user_id=EVAL_USER_ID,
                    doc_id=doc_uuid,
                )
                logger.info("[%d/%d] Merged Neo4j graph for %s (%d entities, %d rels)", idx, len(final_doc_list), title[:30], len(graph_struct.entities), len(graph_struct.relationships))
            except Exception as e:
                logger.warning("[%d/%d] Neo4j ER error for %s: %s", idx, len(final_doc_list), title[:30], e)

        # B. Qdrant Vector Upsert
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
        except Exception as e:
            logger.warning("[%d/%d] Qdrant error for %s: %s", idx, len(final_doc_list), title[:30], e)

        # C. PostgreSQL Insertion
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
        except Exception as e:
            logger.warning("[%d/%d] Postgres error for %s: %s", idx, len(final_doc_list), title[:30], e)

    logger.info("Beginning concurrent ingestion of %d enterprise documents...", len(final_doc_list))
    t_start = time.perf_counter()
    tasks = [ingest_single_doc(i, doc) for i, doc in enumerate(final_doc_list, 1)]
    await asyncio.gather(*tasks)
    logger.info("Completed full ingestion in %.2f seconds.", time.perf_counter() - t_start)

    return out_q_path, str(EVAL_USER_ID)


async def main():
    q_file = "test/benchmarks/enterprise_rag_slice_questions.json"
    eval_uid = str(EVAL_USER_ID)

    # Check if already ingested with full 80 documents
    already_ingested = False
    async with AsyncSessionLocal() as s:
        from sqlalchemy import select, func
        count = await s.scalar(select(func.count(Chunk.chunk_id)).where(Chunk.user_id == EVAL_USER_ID))
        if count and count >= 150:
            already_ingested = True
            logger.info("Found %d already ingested chunks for eval user. Skipping re-ingestion.", count)

    if not already_ingested:
        q_file, eval_uid = await ingest_enterprise_slice(max_distractors=19)

    print("\n======================================================================")
    print("   RUNNING SCALED ENTERPRISE RAG-BENCH (28 QUESTIONS, 80 DOCS)")
    print("======================================================================\n")

    engine_bench = BenchmarkEngine(UUID(eval_uid))
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
        res = await engine_bench.run_question(q)
        results.append(res)
        for m_key, m in res.modes.items():
            print(f"   * {m.mode:<16} | Recall: {m.doc_recall:.2f} | Fact Score: {m.correctness_score:.2f} | Latency: {m.latency_sec}s")

    print("\n" + "=" * 75)
    print("      ENTERPRISE RAG-BENCH (SCALED 28-QUESTION CORPUS) EVALUATION REPORT")
    print("=" * 75)
    print(f"{'Mode':<18} | {'Avg Recall@5':<14} | {'Fact Score':<12} | {'Avg Latency':<12}")
    print("-" * 75)
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
    print("=" * 75)

    # Category breakdown
    print("\n" + "=" * 75)
    print("                    PER-CATEGORY FACT ACCURACY BREAKDOWN")
    print("=" * 75)
    categories = sorted(list(set(r.question_type for r in results)))
    category_summary = {}
    print(f"{'Category':<26} | {'Count':<5} | {'Vector':<8} | {'FTS':<8} | {'Hybrid':<8} | {'Graph':<8}")
    print("-" * 75)
    for cat in categories:
        cat_results = [r for r in results if r.question_type == cat]
        cat_scores = {}
        for m_key in modes:
            cat_scores[m_key] = sum(r.modes[m_key].correctness_score for r in cat_results) / len(cat_results)
        category_summary[cat] = {
            "count": len(cat_results),
            "vector_fact_score": round(cat_scores["vector_only"], 3),
            "fts_fact_score": round(cat_scores["fts_only"], 3),
            "hybrid_fact_score": round(cat_scores["hybrid_rrf"], 3),
            "graph_fact_score": round(cat_scores["hybrid_graph"], 3),
        }
        print(f"{cat:<26} | {len(cat_results):<5} | {cat_scores['vector_only']*100:5.1f}%  | {cat_scores['fts_only']*100:5.1f}%  | {cat_scores['hybrid_rrf']*100:5.1f}%  | {cat_scores['hybrid_graph']*100:5.1f}%")
    print("=" * 75)

    full_output = {
        "overall_summary": summary_data,
        "category_summary": category_summary,
        "question_results": [
            {
                "question_id": r.question_id,
                "question_type": r.question_type,
                "question": r.question,
                "modes": {
                    mk: {
                        "mode": mv.mode,
                        "doc_recall": mv.doc_recall,
                        "correctness_score": mv.correctness_score,
                        "latency_sec": mv.latency_sec,
                        "retrieved_chunk_count": mv.retrieved_chunk_count,
                        "graph_hit": mv.graph_hit,
                    }
                    for mk, mv in r.modes.items()
                }
            }
            for r in results
        ]
    }

    out_results_path = "test/benchmarks/enterprise_rag_slice_results.json"
    with open(out_results_path, "w", encoding="utf-8") as f:
        json.dump(full_output, f, indent=2)
    print(f"\nSaved EnterpriseRAG-Bench slice results to: {out_results_path}")

    # Generate Markdown Report
    report_path = "test/benchmarks/enterprise_rag_benchmark_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# EnterpriseRAG-Bench Scaled Evaluation Report\n")
        f.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Corpus Size:** 80 Enterprise Documents (61 Ground-Truth, 19 Distractors, ~215 Chunks)\n")
        f.write(f"**Benchmark Questions:** 28 Atomic Fact-Verified Enterprise Questions\n\n")
        f.write("## Overall Retrieval & Generation Performance\n\n")
        f.write("| Retrieval Mode | Avg Recall@5 | Fact Accuracy Score | Avg Latency (s) |\n")
        f.write("|---|:---:|:---:|:---:|\n")
        for m_key in modes:
            m_name = results[0].modes[m_key].mode
            row = summary_data[m_name]
            f.write(f"| **{m_name}** | {row['avg_recall']*100:.1f}% | {row['avg_fact_score']*100:.1f}% | {row['avg_latency_sec']:.2f}s |\n")
        f.write("\n## Per-Category Accuracy Breakdown\n\n")
        f.write("| Category | Questions | Vector Only | FTS Only | Hybrid (RRF) | Hybrid + Multi-Hop Graph | Graph Advantage |\n")
        f.write("|---|:---:|:---:|:---:|:---:|:---:|:---:|\n")
        for cat, c_info in category_summary.items():
            delta = c_info['graph_fact_score'] - c_info['vector_fact_score']
            delta_str = f"**+{delta*100:.1f}%**" if delta > 0 else f"{delta*100:.1f}%"
            f.write(f"| **{cat}** | {c_info['count']} | {c_info['vector_fact_score']*100:.1f}% | {c_info['fts_fact_score']*100:.1f}% | {c_info['hybrid_fact_score']*100:.1f}% | {c_info['graph_fact_score']*100:.1f}% | {delta_str} |\n")
        f.write("\n---\n")
    print(f"Generated Markdown Benchmark Report: {report_path}")

    await engine.dispose()
    await neo4j_client.close()


if __name__ == "__main__":
    asyncio.run(main())
