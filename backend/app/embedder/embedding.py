import logging

from sentence_transformers import SentenceTransformer

from backend.app.exceptions import EmbeddingError

logger = logging.getLogger(__name__)

def generate_embedding(chunks: list[str]):
    try:
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

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
    