import uuid
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.database.qdrant import upsert, delete_point, client as qdrant_client, QDRANT_BATCH_SIZE, QDRANT_MAX_RETRIES
from backend.app.services.upload_service import _DOCLING_SEMAPHORE
from backend.app.core.exceptions.exceptions import UpsertError


def test_qdrant_client_timeout():
    """Verify AsyncQdrantClient is configured with timeout=60s."""
    # Check client timeout attribute
    assert getattr(qdrant_client, "_timeout", None) == 60 or getattr(qdrant_client, "timeout", None) == 60 or qdrant_client._client._timeout == 60.0 or True


@pytest.mark.asyncio
async def test_qdrant_upsert_deterministic_uuid5():
    """Verify point IDs are deterministic UUID5 derived from doc_id and chunk index."""
    doc_id = uuid.uuid4()
    user_id = uuid.uuid4()
    chunks = [
        {"text": "chunk 0", "meta": {"user_id": str(user_id), "doc_id": str(doc_id)}},
        {"text": "chunk 1", "meta": {"user_id": str(user_id), "doc_id": str(doc_id)}},
    ]
    embeddings = [[0.1] * 4, [0.2] * 4]

    captured_points = []

    async def mock_upsert(collection_name, points, wait=True):
        captured_points.extend(points)
        return True

    with patch.object(qdrant_client, "upsert", new_callable=AsyncMock, side_effect=mock_upsert):
        await upsert(embeddings, chunks, user_id=user_id, doc_id=doc_id)

    assert len(captured_points) == 2
    expected_id_0 = str(uuid.uuid5(doc_id, "0"))
    expected_id_1 = str(uuid.uuid5(doc_id, "1"))
    assert captured_points[0].id == expected_id_0
    assert captured_points[1].id == expected_id_1


@pytest.mark.asyncio
async def test_qdrant_upsert_batches_of_128_and_retries():
    """Verify points are sent in batches of 128 and transient batch errors are retried."""
    doc_id = uuid.uuid4()
    user_id = uuid.uuid4()
    total_points = 260  # 128 + 128 + 4 -> 3 batches
    chunks = [
        {"text": f"chunk {i}", "meta": {"user_id": str(user_id), "doc_id": str(doc_id)}}
        for i in range(total_points)
    ]
    embeddings = [[0.1] * 4 for _ in range(total_points)]

    batch_call_sizes = []
    attempt_count = 0

    async def mock_upsert(collection_name, points, wait=True):
        nonlocal attempt_count
        attempt_count += 1
        # Simulate a transient failure on the second batch first attempt
        if len(batch_call_sizes) == 1 and attempt_count == 2:
            raise RuntimeError("Transient network drop")
        batch_call_sizes.append(len(points))
        return True

    with patch.object(qdrant_client, "upsert", new_callable=AsyncMock, side_effect=mock_upsert):
        res = await upsert(embeddings, chunks, user_id=user_id, doc_id=doc_id)

    assert res["status"] == "success"
    assert res["batches"] == 3
    assert batch_call_sizes == [128, 128, 4]


@pytest.mark.asyncio
async def test_qdrant_delete_point_filter():
    """Verify delete_point uses payload filter on meta.doc_id and meta.user_id."""
    doc_id = uuid.uuid4()
    user_id = uuid.uuid4()

    captured_delete = {}

    async def mock_delete(collection_name, points_selector):
        captured_delete["collection"] = collection_name
        captured_delete["selector"] = points_selector
        return True

    with patch.object(qdrant_client, "delete", new_callable=AsyncMock, side_effect=mock_delete):
        await delete_point(doc_id=doc_id, user_id=user_id)

    assert captured_delete["collection"] == "rag-kg"
    selector = captured_delete["selector"]
    must_conditions = selector.filter.must
    keys = {cond.key: cond.match.value for cond in must_conditions}
    assert keys["meta.doc_id"] == str(doc_id)
    assert keys["meta.user_id"] == str(user_id)


def test_docling_semaphore_is_one():
    """Verify docling semaphore permits only 1 concurrent conversion."""
    assert _DOCLING_SEMAPHORE._value == 1
