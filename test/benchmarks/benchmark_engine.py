import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from uuid import UUID
from dataclasses import dataclass, asdict

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sentence_transformers import SentenceTransformer
from sqlalchemy.ext.asyncio import AsyncSession

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

# Set offline mode for HF to avoid repetitive HEAD queries
os.environ["HF_HUB_OFFLINE"] = "1"

logger = logging.getLogger("benchmark")
logging.basicConfig(level=logging.INFO)


@dataclass
class ModeResult:
    mode: str
    retrieved_doc_ids: list[str]
    retrieved_chunk_count: int
    doc_recall: float
    graph_entities_found: list[str]
    graph_hit: bool
    generated_answer: str
    correctness_score: float  # 0.0 to 1.0 (proportion of answer_facts satisfied)
    latency_sec: float


@dataclass
class QuestionBenchmarkResult:
    question_id: str
    question_type: str
    question: str
    modes: dict[str, ModeResult]


class BenchmarkEngine:

    def __init__(self, user_id: UUID):
        self.user_id = user_id
        logger.info("Initializing SentenceTransformer embedding model...")
        try:
            self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", local_files_only=True)
        except Exception:
            self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        self.llm = LLMClient()

    async def judge_answer(self, question: str, generated_answer: str, answer_facts: list[str]) -> float:
        """
        Uses LLM as a judge to verify how many of the ground-truth facts are satisfied.
        Follows the EnterpriseRAG-Bench atomic fact verification methodology.
        """
        if not answer_facts:
            # For negative / info_not_found questions: check if system correctly declined
            decline_phrases = ["not contain", "not found", "does not state", "unanswerable", "not available", "no information"]
            is_refusal = any(p in generated_answer.lower() for p in decline_phrases)
            return 1.0 if is_refusal else 0.0

        facts_text = "\n".join(f"- Fact {i+1}: {fact}" for i, fact in enumerate(answer_facts))
        judge_prompt = f"""
You are an impartial evaluator grading an AI assistant's answer against gold ground-truth facts.

[Question]
{question}

[Assistant Answer]
{generated_answer}

[Gold Ground-Truth Facts]
{facts_text}

For each fact above, decide whether the Assistant Answer accurately includes or entails it (YES or NO).
Return ONLY a valid JSON object in this format:
{{
  "evaluations": [
    {{"fact_index": 1, "supported": true}},
    {{"fact_index": 2, "supported": false}}
  ]
}}
"""
        try:
            resp = await self.llm._client.chat.completions.create(
                model=self.llm._config.model,
                messages=[{"role": "user", "content": judge_prompt}],
                response_format={"type": "json_object"},
                temperature=0.0,
                timeout=25.0,
            )
            raw = resp.choices[0].message.content
            data = json.loads(raw)
            evals = data.get("evaluations", [])
            if not evals:
                return 0.5
            supported_count = sum(1 for e in evals if e.get("supported") is True)
            return round(supported_count / len(answer_facts), 2)
        except Exception as e:
            logger.warning("Judge scoring error: %s", e)
            return 0.5

    async def run_question(self, q_item: dict) -> QuestionBenchmarkResult:
        query_text = q_item["question"]
        expected_docs = set(str(d).lower() for d in q_item.get("expected_doc_ids", []))
        expected_entities = [e.lower() for e in q_item.get("expected_entities", [])]
        answer_facts = q_item.get("answer_facts", [])
        chat_req = ChatRequest(query=query_text)

        modes_result = {}

        # ---------------- 1. Vector Search Only ----------------
        t0 = time.perf_counter()
        vec_results = await vector_search(chat_req, self.user_id, self.model)
        vec_docs = [str(r.get("doc_id", "")).lower() for r in vec_results if r.get("doc_id")]
        vec_recall = (
            1.0 if not expected_docs else (len(expected_docs.intersection(vec_docs)) / len(expected_docs))
        )
        vec_answer = await self.llm.generate(query_text, vec_results[:5], [])
        t_vec = time.perf_counter() - t0
        vec_score = await self.judge_answer(query_text, vec_answer, answer_facts)
        modes_result["vector_only"] = ModeResult(
            mode="Vector Only",
            retrieved_doc_ids=list(dict.fromkeys(vec_docs[:5])),
            retrieved_chunk_count=len(vec_results),
            doc_recall=round(vec_recall, 2),
            graph_entities_found=[],
            graph_hit=False,
            generated_answer=vec_answer,
            correctness_score=vec_score,
            latency_sec=round(t_vec, 2),
        )

        # ---------------- 2. FTS Search Only ----------------
        t0 = time.perf_counter()
        async with AsyncSessionLocal() as db:
            fts_results = await fts_search(chat_req, self.user_id, db)
        fts_docs = [str(r.get("doc_id", "")).lower() for r in fts_results if r.get("doc_id")]
        fts_recall = (
            1.0 if not expected_docs else (len(expected_docs.intersection(fts_docs)) / len(expected_docs))
        )
        fts_answer = await self.llm.generate(query_text, fts_results[:5], [])
        t_fts = time.perf_counter() - t0
        fts_score = await self.judge_answer(query_text, fts_answer, answer_facts)
        modes_result["fts_only"] = ModeResult(
            mode="FTS Only",
            retrieved_doc_ids=list(dict.fromkeys(fts_docs[:5])),
            retrieved_chunk_count=len(fts_results),
            doc_recall=round(fts_recall, 2),
            graph_entities_found=[],
            graph_hit=False,
            generated_answer=fts_answer,
            correctness_score=fts_score,
            latency_sec=round(t_fts, 2),
        )

        # ---------------- 3. Hybrid RRF Search ----------------
        t0 = time.perf_counter()
        rrf_results = rrf_fuse(vec_results, fts_results)
        rrf_docs = [str(r.get("doc_id", "")).lower() for r in rrf_results if r.get("doc_id")]
        rrf_recall = (
            1.0 if not expected_docs else (len(expected_docs.intersection(rrf_docs[:10])) / len(expected_docs))
        )
        hybrid_answer = await self.llm.generate(query_text, rrf_results[:5], [])
        t_rrf = time.perf_counter() - t0
        rrf_score = await self.judge_answer(query_text, hybrid_answer, answer_facts)
        modes_result["hybrid_rrf"] = ModeResult(
            mode="Hybrid (RRF)",
            retrieved_doc_ids=list(dict.fromkeys(rrf_docs[:5])),
            retrieved_chunk_count=len(rrf_results),
            doc_recall=round(rrf_recall, 2),
            graph_entities_found=[],
            graph_hit=False,
            generated_answer=hybrid_answer,
            correctness_score=rrf_score,
            latency_sec=round(t_rrf, 2),
        )

        # ---------------- 4. Hybrid + Neo4j Graph Search ----------------
        t0 = time.perf_counter()
        doc_ids_for_graph = extract_doc_ids(rrf_results, 10)
        try:
            graph_records = await graph_search(chat_req, self.user_id, doc_ids_for_graph)
        except Exception as e:
            logger.warning("Graph search exception: %s", e)
            graph_records = []

        found_entities = []
        for r in graph_records:
            d = r.data() if hasattr(r, "data") else dict(r)
            for v in d.values():
                if isinstance(v, str):
                    found_entities.append(v)

        graph_hit = any(
            any(exp in fe.lower() for fe in found_entities)
            for exp in expected_entities
        ) if expected_entities else False

        full_answer = await self.llm.generate(query_text, rrf_results[:5], graph_records)
        t_graph = time.perf_counter() - t0
        graph_score = await self.judge_answer(query_text, full_answer, answer_facts)

        modes_result["hybrid_graph"] = ModeResult(
            mode="Hybrid + Graph",
            retrieved_doc_ids=list(dict.fromkeys(rrf_docs[:5])),
            retrieved_chunk_count=len(rrf_results) + len(graph_records),
            doc_recall=round(rrf_recall, 2),
            graph_entities_found=found_entities[:8],
            graph_hit=graph_hit,
            generated_answer=full_answer,
            correctness_score=graph_score,
            latency_sec=round(t_graph, 2),
        )

        return QuestionBenchmarkResult(
            question_id=q_item["question_id"],
            question_type=q_item["question_type"],
            question=query_text,
            modes=modes_result,
        )


async def run_benchmark(questions_file: str, user_id_str: str, output_file: str | None = None):
    with open(questions_file, "r", encoding="utf-8") as f:
        questions = json.load(f)

    user_id = UUID(user_id_str)
    engine = BenchmarkEngine(user_id)

    print(f"\n=======================================================")
    print(f"  RUNNING BENCHMARK ON CORPUS ({len(questions)} Questions)")
    print(f"  Target User ID: {user_id}")
    print(f"=======================================================\n")

    results: list[QuestionBenchmarkResult] = []

    for idx, q in enumerate(questions, 1):
        print(f"[{idx}/{len(questions)}] Evaluating: {q['question_id']} ({q['question_type']})...")
        res = await engine.run_question(q)
        results.append(res)
        for mode_key, m in res.modes.items():
            print(f"   * {m.mode:<16} | Recall: {m.doc_recall:.2f} | Fact Score: {m.correctness_score:.2f} | Latency: {m.latency_sec}s")

    # Aggregate summaries
    print("\n" + "=" * 70)
    print("                    BENCHMARK SUMMARY REPORT")
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

    # Save output
    if output_file:
        serializable = [
            {
                "question_id": r.question_id,
                "question_type": r.question_type,
                "question": r.question,
                "modes": {k: asdict(v) for k, v in r.modes.items()},
            }
            for r in results
        ]
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({"summary": summary_data, "results": serializable}, f, indent=2)
        print(f"\nDetailed benchmark results saved to: {output_file}")


if __name__ == "__main__":
    import sys
    q_file = sys.argv[1] if len(sys.argv) > 1 else "test/benchmarks/existing_corpus_questions.json"
    uid = sys.argv[2] if len(sys.argv) > 2 else "a92bcf77-5f8d-4efe-a425-6bf9159c01ad"
    out = sys.argv[3] if len(sys.argv) > 3 else "test/benchmarks/existing_corpus_results.json"
    asyncio.run(run_benchmark(q_file, uid, out))
