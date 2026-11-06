import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from sentence_transformers import SentenceTransformer
from docling.document_converter import DocumentConverter

from backend.app.database.neo4j import neo4j_client

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize embedding model
    embed_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    app.state.embedder = embed_model
    app.state.extractor = DocumentConverter()

    # Pre-cache Docling chunker tokenizer before disabling network requests
    from backend.app.chunker.docling import _chunker

    # Prevent HuggingFace Hub HEAD requests on every chunking and embedding call
    os.environ["HF_HUB_OFFLINE"] = "1"

    # Initialize Neo4j indexes and constraints
    try:
        await neo4j_client.init_schema()
    except Exception as e:
        logger.error("Failed to initialize Neo4j schema: %s", e)

    yield

    # Lifespan teardown: guard with hasattr before deleting state attributes
    for attr in ("DocumentConverter", "extractor", "embedder"):
        if hasattr(app.state, attr):
            delattr(app.state, attr)

    await neo4j_client.close()
