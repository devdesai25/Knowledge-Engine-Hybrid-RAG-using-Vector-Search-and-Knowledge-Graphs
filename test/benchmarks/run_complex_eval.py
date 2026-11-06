import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from uuid import UUID

from sentence_transformers import SentenceTransformer

# Ensure paths
BENCHMARK_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BENCHMARK_DIR.parent.parent
if str(BENCHMARK_DIR) not in sys.path:
    sys.path.insert(0, str(BENCHMARK_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.database.neo4j import neo4j_client
from backend.app.settings import setting
from backend.app.database.supabase import AsyncSessionLocal
from backend.app.schema.chat import ChatRequest
from backend.app.services.chat_service import (
    vector_search,
    fts_search,
    rrf_fuse,
    extract_doc_ids,
    graph_search,
)
from backend.app.llm.client import LLMClient
from benchmark_engine import BenchmarkEngine

os.environ["HF_HUB_OFFLINE"] = "1"
logging.basicConfig(level=logging.WARNING)

USER_ID = UUID("a92bcf77-5f8d-4efe-a425-6bf9159c01ad")
QUESTIONS_FILE = "test/benchmarks/complex_benchmark_questions.json"
REPORT_FILE = "test/benchmarks/complex_eval_report.md"


def log(msg=""):
    print(msg, flush=True)


async def main():
    log("=" * 80)
    log("   ADVANCED MULTI-HOP & STRUCTURAL REASONING BENCHMARK: VECTOR VS. GRAPH")
    log("=" * 80)
    log(f"Target User ID: {USER_ID}\n")

    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)

    engine = BenchmarkEngine(USER_ID)
    report_lines = [
        "# Advanced Multi-Hop & Structural Knowledge Graph Benchmark",
        f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Target Corpus:** Legal Statutes (BSA 2023, Water Act 1974) & Distributed/Compiler Systems",
        "",
        "| # | Question Title | Vector Fact Score | Graph Fact Score | Graph Advantage |",
        "|---|---|:---:|:---:|:---:|",
    ]

    summary_rows = []

    for idx, q in enumerate(questions, 1):
        q_id = q["question_id"]
        title = q["title"]
        query_text = q["question"]
        answer_facts = q["answer_facts"]
        chat_req = ChatRequest(query=query_text)

        log(f"\n[{idx}/{len(questions)}] Challenge: {title}")
        log(f"Question: \"{query_text}\"")

        # 1. Run Vector Search Only
        t_v0 = time.perf_counter()
        vec_results = await vector_search(chat_req, USER_ID, engine.model)
        vec_answer = await engine.llm.generate(query_text, vec_results[:5], [])
        t_vec = time.perf_counter() - t_v0
        vec_score = await engine.judge_answer(query_text, vec_answer, answer_facts)

        # 2. Run Hybrid + Graph Search
        t_g0 = time.perf_counter()
        async with AsyncSessionLocal() as db:
            fts_results = await fts_search(chat_req, USER_ID, db)
        rrf_results = rrf_fuse(vec_results, fts_results)
        doc_ids = extract_doc_ids(rrf_results, 10)

        graph_records = []
        try:
            graph_records = await graph_search(chat_req, USER_ID, doc_ids)
        except Exception as e:
            log(f"  [Graph Error]: {e}")

        graph_answer = await engine.llm.generate(query_text, rrf_results[:5], graph_records)
        t_graph = time.perf_counter() - t_g0
        graph_score = await engine.judge_answer(query_text, graph_answer, answer_facts)

        delta = round((graph_score - vec_score) * 100, 1)
        delta_str = f"+{delta}%" if delta > 0 else f"{delta}%"

        log(f"  -> Vector Only Fact Score : {vec_score * 100:.1f}% ({t_vec:.2f}s)")
        log(f"  -> Hybrid + Graph Score   : {graph_score * 100:.1f}% ({t_graph:.2f}s)")
        log(f"  -> Graph Value-Add Delta  : {delta_str}")
        log(f"  -> Graph Records Found    : {len(graph_records)} records")

        # Print top extracted graph entities
        extracted_entities = []
        for r in graph_records[:6]:
            d = r.data() if hasattr(r, "data") else dict(r)
            extracted_entities.append(str(d))
        if extracted_entities:
            log("  -> Sample Graph Traversal Context:")
            for ent in extracted_entities[:3]:
                log(f"      * {ent}")

        report_lines.append(
            f"| {idx} | {title} | {vec_score * 100:.1f}% | {graph_score * 100:.1f}% | **{delta_str}** |"
        )

        summary_rows.append({
            "id": q_id,
            "title": title,
            "question": query_text,
            "vec_score": vec_score,
            "graph_score": graph_score,
            "delta": delta,
            "vec_answer": vec_answer,
            "graph_answer": graph_answer,
            "graph_records": extracted_entities,
            "answer_facts": answer_facts,
        })

    # Summary table
    avg_vec = sum(r["vec_score"] for r in summary_rows) / len(summary_rows) * 100
    avg_graph = sum(r["graph_score"] for r in summary_rows) / len(summary_rows) * 100
    avg_delta = avg_graph - avg_vec

    log("\n" + "=" * 80)
    log("                     OVERALL COMPLEX BENCHMARK RESULTS")
    log("=" * 80)
    log(f"  Average Vector Only Fact Score     : {avg_vec:.1f}%")
    log(f"  Average Hybrid + Graph Fact Score  : {avg_graph:.1f}%")
    log(f"  OVERALL KNOWLEDGE GRAPH VALUE-ADD : +{avg_delta:.1f}% ABSOLUTE GAIN")
    log("=" * 80)

    report_lines.extend([
        "",
        "## Summary",
        f"- **Average Vector-Only Accuracy:** {avg_vec:.1f}%",
        f"- **Average Hybrid + Graph Accuracy:** {avg_graph:.1f}%",
        f"- **Net Knowledge Graph Advantage:** **+{avg_delta:.1f}%**",
        "",
        "---",
        "## Deep-Dive Question Analysis",
    ])

    for row in summary_rows:
        report_lines.extend([
            f"### {row['title']}",
            f"**Question:** {row['question']}",
            "",
            f"- **Vector Fact Score:** {row['vec_score'] * 100:.1f}%",
            f"- **Graph Fact Score:** {row['graph_score'] * 100:.1f}% (Delta: **{row['delta']:+.1f}%**)",
            "",
            "#### Graph Traversal Evidence (Neo4j Records Retrieved):",
            "```json",
            json.dumps(row["graph_records"], indent=2),
            "```",
            "",
            "#### Side-by-Side Comparison:",
            "**Vector Only Answer:**",
            f"> {row['vec_answer'].replace(chr(10), ' ')}",
            "",
            "**Hybrid + Knowledge Graph Answer:**",
            f"> {row['graph_answer'].replace(chr(10), ' ')}",
            "",
            "---",
        ])

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    log(f"\nDetailed Markdown report written to: {REPORT_FILE}")
    await neo4j_client.close()


if __name__ == "__main__":
    asyncio.run(main())
