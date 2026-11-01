# Knowledge Engine: Hybrid RAG using Vector Search and Knowledge Graphs

Building a production-ready Knowledge Engine from scratch.

## Overview

This project implements a hybrid Retrieval-Augmented Generation (RAG) system that combines semantic retrieval from vector search with structured retrieval from a knowledge graph. The objective is to build a knowledge-centric assistant that can ground its responses in relevant evidence, reason over connected entities, and answer questions with better traceability and higher precision than a purely vector-based retrieval pipeline.

The repository is organized as a modular backend service for document ingestion, chunking, embedding, retrieval, graph enhancement, and LLM-based answer generation. It is designed as a real-world foundation for a production-ready knowledge engine rather than a lightweight demo.

## Why this project exists

Many document Q&A systems rely only on vector similarity search, which is strong for semantic retrieval but weak when answers require multi-hop reasoning, entity linking, or understanding relationships between concepts. This project addresses that gap by combining:

- vector retrieval for semantic matching
- knowledge graph reasoning for structured relationships
- LLM-based synthesis for final answer generation

The result is a hybrid architecture intended to improve retrieval quality, explainability, and answer relevance for complex knowledge workflows.

## Current implementation

The repository currently includes the foundation for a Python-based hybrid RAG backend, including:

- FastAPI application setup
- Pydantic-based configuration management
- modular pipeline components for chunking, embedding, extraction, normalization, and retrieval
- Qdrant integration for vector search
- Google Gemini API integration for LLM-based reasoning
- route-based backend structure for upload and chat workflows

## Architecture

The system is organized into the following major components:

- document ingestion and preprocessing
- chunking and normalization
- embedding generation
- semantic retrieval from vector storage
- knowledge extraction and graph construction
- hybrid retrieval combining semantic and graph signals
- LLM-based answer generation
- API endpoints for document upload and query workflows

## Tech stack

- Python
- FastAPI
- Uvicorn
- Pydantic and pydantic-settings
- Qdrant
- Hugging Face integrations
- Google Gemini API
- hybrid RAG architecture
- knowledge graph retrieval concepts

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
- a Qdrant instance
- a Gemini API key
- a Hugging Face token if your model configuration requires one

## Environment variables

Create a `.env` file in the project root or backend directory with values similar to:

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

The project exposes a FastAPI application intended for document ingestion and chat-based retrieval workflows. The exact route names and payload structures should be verified in the files under `backend/app/routes` before using them in production or integration tests.

## Roadmap

This project is under active development. The items below are planned work, grouped by theme and listed roughly in priority order. Anything not yet measured is treated as a hypothesis, and changes are kept only if they improve results on the evaluation set.

### 1. Security and correctness

- Tenant isolation across every store. Enforce a required `user_id` filter in Qdrant, Postgres full-text search, and Neo4j, including every node along a graph path. Entities are scoped per user so one user's documents can never be linked to another's.
- Automated isolation tests. Run against real Qdrant, Postgres, and Neo4j containers. For every store and every end-to-end API flow, one user's queries must never return another user's data.
- Authentication and role-based access. JWT login with tenant and user derived from the token, never from the request body. Document upload and deletion are restricted to admins.
- Hardening. Rate limiting, upload validation for type and size, secrets managed in environment variables, and treatment of document text as untrusted input to defend against prompt injection.
- Safer graph querying. Replace LLM-written Cypher and substring-based validation with parameterized, templated queries.

### 2. Evaluation

- Evaluation set. roughly 40 to 60 hand-verified questions covering single-fact, exact-match, semantic, multi-hop, aggregation, unanswerable, and cross-tenant cases, split into development and held-out test sets.
- Metrics. Recall@k, whether all gold documents were retrieved, MRR, answer correctness, faithfulness, refusal accuracy, p50/p95 latency, and LLM calls and tokens per query.
- Baselines and ablations. Compare vector-only, hybrid (vector + keyword + RRF), hybrid + graph, and hybrid + graph + reranker, and publish the results table in this README.
- Regression gate. Run the evaluation in CI so a change that lowers retrieval quality cannot be merged unnoticed.

### 3. Retrieval quality

- Cross-encoder reranking over the fused and expanded candidate set.
- Hybrid search tuning. Tune fusion parameters and candidate limits according to evaluation results.
- Reduced latency. Move embedding off the event loop, cache the graph schema, run retrieval stages concurrently, and stream the answer as it is generated.

### 4. Knowledge graph

- Entity resolution at ingestion. Normalize names and aliases first, with embedding-based deduplication as a later step.
- Multi-hop retrieval as candidate generation. Top documents from fusion act as seeds, not filters. Templated two-hop expansion with degree caps, scoring, and fetching chunks for reranking and generation.
- Bounded fallback. If reranker confidence is low, an optional agent restricted to a small set of typed tools can be used with a strict step budget. This is kept only if the quality gain justifies the added latency.
- Metadata over graph nodes. Course and chapter information lives in document and chunk metadata rather than in the graph.

### 5. Production readiness

- Reliability. Per-stage timeouts, retries with backoff on LLM calls, and automatic fallback to hybrid retrieval if the graph step fails so the API never returns a 500 because of an optional component.
- Asynchronous ingestion with a job queue, status tracking, and idempotent re-processing.
- Observability. Structured logs with request IDs and per-stage timings, tracing, and cost and token tracking.
- Delivery. Docker and Docker Compose setup, database migrations, health checks, CI, linting, type checking, and a short operations runbook.

### 6. Product

- Web frontend: login, streaming chat with clickable source citations, a document library, and an admin screen for user management.
- Multi-tenant document management: list, delete, and re-ingest documents per organization, with all users in an organization able to query its documents.
- Code-aware ingestion: AST-based parsing for source code so the assistant can answer questions about codebases as well as documents.

## Known limitations

- The knowledge-graph components are still being built, so retrieval quality numbers for the graph-augmented pipeline will be added once they are measured.
- End-to-end latency is currently several seconds per query and will be reduced as part of the work above.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## Contributing

Contributions, issues, and feature requests are welcome.

## Contact

Developer: devdesai25
Repository: https://github.com/devdesai25/Knowledge-Engine-Hybrid-RAG-using-Vector-Search-and-Knowledge-Graphs
