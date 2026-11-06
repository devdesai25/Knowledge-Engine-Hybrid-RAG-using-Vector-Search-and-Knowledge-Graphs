import logging

from fastapi import Request
from sentence_transformers import SentenceTransformer

from backend.app.core.exceptions.exceptions import EmbeddingError

logger = logging.getLogger(__name__)

def generate_embedding(chunks: list[str], model):
    try:

        emebeddings = model.encode(
            chunks,
            normalize_embeddings=True
        )

        return emebeddings
    
                
    except Exception as e:

        logger.info(
            "Failed Processing file:"
        )

        raise EmbeddingError(
            "Failed to generate embedding"
        ) from e
    