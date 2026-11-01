# Knowledge Engine: Hybrid RAG using Vector Search and Knowledge Graphs

Building a production-ready Knowledge Engine from scratch.

## Overview

This project implements a hybrid Retrieval-Augmented Generation (RAG) system that combines semantic retrieval from vector search with structured retrieval from a knowledge graph. The goal is to build a knowledge-centric assistant that can retrieve the right evidence, reason over it, and answer questions with higher precision and better traceability than a purely vector-based system.

The project is designed around a modular backend architecture that separates ingestion, chunking, embedding, graph extraction, retrieval, and LLM orchestration. It is intended as a real-world foundation for a production-ready knowledge engine rather than a toy demo.

## Current implementation

The repository currently contains the backend structure for a Python-based hybrid RAG application, including:

- FastAPI application entrypoint
- Pydantic-based settings management
- Modular app packages for chunking, embedding, extraction, normalization, database access, and LLM integration
- Qdrant configuration for vector retrieval
- Gemini API integration for LLM-based reasoning
- Route-based API structure for upload and chat workflows

## Architecture

The system is organized around the following high-level components:

- Document ingestion and preprocessing
- Chunking and normalization
- Embedding generation
- Semantic retrieval from Qdrant
- Knowledge extraction and graph construction
- Hybrid retrieval combining vector and graph signals
- LLM-based answer generation
- API access for upload and chat workflows

## Tech stack

- Python
- FastAPI
- Uvicorn
- Pydantic
- Qdrant
- Hugging Face model integrations
- Google Gemini API
- Hybrid retrieval architecture
- Knowledge graph concepts and graph-aware retrieval

## Project structure

```bash
.
├── backend/
│   ├── app/
│   │   ├── chunker/
│   │   ├── core/
│   │   ├── database/
│   │   ├── embedder/
│   │   ├── extractor/
│   │   ├── llm/
│   │   ├── normalizer/
│   │   ├── routes/
│   │   ├── schema/
│   │   ├── services/
│   │   ├── exceptions.py
│   │   ├── main.py
│   │   ├── settings.py
│   │   └── __init__.py
│   ├── requirements.txt
├── LICENSE
├── README.md
├── .gitignore
└── .env.example
```

## Prerequisites

Before running the project, make sure you have:

- Python 3.10 or later
- pip
- A Qdrant instance
- A Gemini API key
- Hugging Face token if required by your model setup

## Environment variables

Create a `.env` file in the project root or backend directory with values such as:

```env
HF_TOKEN=your_huggingface_token
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_qdrant_api_key
GEMINI_API_KEY=your_gemini_api_key
```

## Installation

```bash
git clone https://github.com/devdesai25/Knowledge-Engine-Hybrid-RAG-using-Vector-Search-and-Knowledge-Graphs.git
cd Knowledge-Engine-Hybrid-RAG-using-Vector-Search-and-Knowledge-Graphs

python -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

## Running the application

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then open:

```text
http://localhost:8000/docs
```

for the FastAPI Swagger UI.

## API usage

This project currently exposes a FastAPI application structure intended for document ingestion and chat-based retrieval workflows. The exact route surface should be confirmed from the files under `backend/app/routes`.

## Roadmap

This project is under active development. The items below are planned work, grouped by theme and listed roughly in priority order. Anything not yet measured is treated as a hypothesis, and changes are kept only if they improve results on the evaluation set.

### 1. Security and correctness

- Tenant isolation across every store. Enforce a required `user_id` filter in Qdrant, Postgres full-text search and Neo4j, including every node along a graph path. Entities are scoped per user, so one user's documents can never be linked to another's.
- Automated isolation tests. Run against real Qdrant, Postgres and Neo4j containers: for every store and end to end through the API, one user's queries must never return another user's data.
- Authentication and role-based access. JWT login with tenant and user taken from the token, never from the request body. Document upload and deletion are restricted to admins.
- Hardening. Rate limiting, upload validation (type and size), secrets kept in environment variables, and treating all document text as untrusted input to defend against prompt injection.
- Safer graph querying. Replace LLM-written Cypher and substring-based validation with parameterised, templated queries.

### 2. Evaluation

- Evaluation set. Roughly 40-60 hand-verified questions covering single-fact, exact-match, semantic, multi-hop, aggregation, unanswerable and cross-tenant cases, split into development and held-out test sets.
- Metrics. Recall@k, whether all gold documents were retrieved, MRR, answer correctness, faithfulness, refusal accuracy, p50/p95 latency, and LLM calls and tokens per query.
- Baselines and ablations. Compare vector-only, hybrid (vector + keyword + RRF), hybrid + graph and hybrid + graph + reranker, and publish the results table in this README.
- Regression gate. Run the evaluation in CI so a change that lowers retrieval quality cannot be merged unnoticed.

### 3. Retrieval quality

- Cross-encoder reranking over the fused and expanded candidate set.
- Hybrid search tuning. Tune fusion parameters and candidate limits using evaluation results.
- Reduced latency. Move embedding off the event loop, cache the graph schema, run retrieval stages concurrently, and stream the answer as it is generated.

### 4. Knowledge graph

- Entity resolution at ingestion. Normalise names and aliases first, with embedding-based deduplication as a later step.
- Multi-hop retrieval as candidate generation. Top documents from fusion act as seeds, not filters. Templated two-hop expansion with degree caps, scoring (personalised PageRank in Python if hub nodes add noise), then fetching chunks for reranking and generation.
- Bounded fallback. If reranker confidence is low, an optional agent restricted to a small set of typed tools (find entities, expand, get chunks) with a strict step budget. This is kept only if the quality gain justifies the added latency.
- Metadata over graph nodes. Course and chapter information lives in document and chunk metadata rather than the graph.

### 5. Production readiness

- Reliability. Per-stage timeouts, retries with backoff on LLM calls, and automatic fallback to hybrid retrieval if the graph step fails, so the API never returns a 500 because of an optional component.
- Asynchronous ingestion with a job queue, status tracking and idempotent re-processing.
- Observability. Structured logs with request IDs and per-stage timings, tracing (OpenTelemetry or Langfuse), and cost and token tracking.
- Delivery. Docker and Docker Compose setup, database migrations, health checks, CI (tests, linting, type checking), and a short operations runbook.

### 6. Product

- Web frontend: login, streaming chat with clickable source citations (filename, page and the exact passage), a document library, and an admin screen for managing users.
- Multi-tenant document management: list, delete and re-ingest documents per organisation, with all users in an organisation able to query its documents.
- Code-aware ingestion: AST-based parsing for source code so the assistant can answer questions about codebases as well as documents.

## Known limitations

- The knowledge-graph components are still being built, so retrieval quality numbers for the graph-augmented pipeline will be added once they are measured.
- End-to-end latency is currently several seconds per query and is being reduced as part of the work above.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## Contributing

Contributions, issues, and feature requests are welcome.

## Contact

Developer: devdesai25
Repository: https://github.com/devdesai25/Knowledge-Engine-Hybrid-RAG-using-Vector-Search-and-Knowledge-Graphs
