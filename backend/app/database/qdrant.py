import uuid
from uuid import UUID
import asyncio
import logging
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.models import PointStruct

from backend.app.settings import setting
from backend.app.core.exceptions.exceptions import UpsertError, DeletionError

logger = logging.getLogger(__name__)

# Configured with timeout=60s to prevent ReadTimeout on large document batch uploads
client = AsyncQdrantClient(
    url=setting.QDRANT_URL,
    api_key=setting.QDRANT_API_KEY,
    timeout=60,
    cloud_inference=True,
)

QDRANT_BATCH_SIZE = 128
QDRANT_MAX_RETRIES = 3


async def upsert(
    embeddings: list[list[float]],
    chunks: list[dict],
    user_id: UUID | str,
    doc_id: UUID | str | None = None,
) -> dict:
    """
    Qdrant client is async.
    Enforces tenant isolation by verifying all chunk payloads match the provided user_id.
    Sends points in batches of 128 with deterministic UUID5 point IDs and up to 3 retries per batch.
    """
    if len(embeddings) != len(chunks):
        raise UpsertError(
            f"Mismatched lengths: {len(embeddings)} embeddings vs {len(chunks)} chunks"
        )

    user_id_str = str(user_id)
    for chunk in chunks:
        meta = chunk.get("meta", {})
        chunk_user_id = meta.get("user_id")
        if chunk_user_id is None or str(chunk_user_id) != user_id_str:
            raise UpsertError(
                f"Tenant isolation violation: chunk user_id {chunk_user_id} does not match {user_id_str}"
            )

    # Resolve document_id for deterministic point IDs (idempotent retries)
    resolved_doc_id = doc_id
    if resolved_doc_id is None and chunks:
        resolved_doc_id = chunks[0].get("meta", {}).get("doc_id")
    if resolved_doc_id is None:
        resolved_doc_id = uuid.uuid4()

    doc_uuid = uuid.UUID(str(resolved_doc_id))

    # Generate deterministic UUID5 point IDs from doc_id and chunk index
    points = [
        PointStruct(
            id=str(uuid.uuid5(doc_uuid, str(i))),
            vector=embedding,
            payload=chunk,
        )
        for i, (embedding, chunk) in enumerate(zip(embeddings, chunks))
    ]

    total_points = len(points)
    total_batches = (total_points + QDRANT_BATCH_SIZE - 1) // QDRANT_BATCH_SIZE if total_points > 0 else 0

    for batch_idx, start_idx in enumerate(range(0, total_points, QDRANT_BATCH_SIZE)):
        batch = points[start_idx:start_idx + QDRANT_BATCH_SIZE]
        for attempt in range(QDRANT_MAX_RETRIES):
            try:
                await client.upsert(
                    collection_name="rag-kg",
                    points=batch,
                    wait=True,
                )
                break
            except Exception as e:
                if attempt < QDRANT_MAX_RETRIES - 1:
                    backoff = 2.0 ** attempt  # 1s, 2s
                    logger.warning(
                        "Qdrant upsert batch %d/%d (%d points) failed (%s: %s). Retrying in %.1fs (attempt %d/%d)...",
                        batch_idx + 1,
                        total_batches,
                        len(batch),
                        type(e).__name__,
                        e,
                        backoff,
                        attempt + 1,
                        QDRANT_MAX_RETRIES,
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error(
                        "Qdrant upsert batch %d/%d failed after %d attempts: %s: %s",
                        batch_idx + 1,
                        total_batches,
                        QDRANT_MAX_RETRIES,
                        type(e).__name__,
                        e,
                    )
                    raise UpsertError(
                        f"Failed to store embeddings in Qdrant (batch {batch_idx + 1}/{total_batches}): {type(e).__name__}: {e}"
                    ) from e

    return {
        "status": "success",
        "points": total_points,
        "batches": total_batches,
    }


async def delete_point(doc_id: UUID | str, user_id: UUID | str):
    """
    Deletes points scoped strictly to both doc_id and user_id using payload filter,
    ensuring cleanup even if timed-out batches only partially landed.
    """
    try:
        await client.delete(
            collection_name="rag-kg",
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="meta.doc_id",
                            match=models.MatchValue(value=str(doc_id)),
                        ),
                        models.FieldCondition(
                            key="meta.user_id",
                            match=models.MatchValue(value=str(user_id)),
                        ),
                    ]
                )
            ),
        )
    except Exception as e:
        logger.error(
            "Failed to delete embeddings for doc_id=%s, user_id=%s (%s: %s)",
            doc_id,
            user_id,
            type(e).__name__,
            e,
        )
        raise DeletionError(f"Failed to delete embeddings: {type(e).__name__}: {e}") from e
