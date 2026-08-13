from uuid import uuid4
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct

from backend.app.settings import setting
from backend.app.exceptions import UpsertError

client = AsyncQdrantClient(
    url=setting.QDRANT_URL,
    api_key=setting.QDRANT_API_KEY,
    cloud_inference=True
)

async def upsert(embeddings, chunks):
    """
    Qdrant client is async
    """
    if len(embeddings) != len(chunks):
        raise UpsertError(
            f"Mismatched lengths: {len(embeddings)} embeddings vs {len(chunks)} chunks"
        )

    try:

        points = [
            PointStruct(
                id=str(uuid4()),
                vector=embedding,
                payload=chunk,
            )
        for embedding, chunk in zip(embeddings, chunks)
        ]

        return await client.upsert(
            collection_name="rag-kg",
            points=points
        )

    except Exception as e:
        raise UpsertError(
            "Failed to store embeddings."
        ) from e