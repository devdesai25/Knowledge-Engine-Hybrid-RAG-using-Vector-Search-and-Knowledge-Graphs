import asyncio
import uuid
import pytest
import pytest_asyncio
from sqlalchemy import select, delete

from backend.app.database.supabase import AsyncSessionLocal
from backend.app.models.user import User
from backend.app.models.bm25_text_search import Document
from backend.app.models.chunks import Chunk
from backend.app.database.qdrant import client as qdrant_client, upsert as qdrant_upsert, delete_point as qdrant_delete
from backend.app.database.neo4j import neo4j_client
from backend.app.schema.chat import ChatRequest
from backend.app.schema.graph import GraphExtraction, Entity, Relationship
from backend.app.services.chat_service import vector_search, fts_search, retrive
from backend.app.core.exceptions.exceptions import UpsertError


@pytest.fixture
def tenant_fixture_data():
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    doc_a_id = uuid.uuid4()
    doc_b_id = uuid.uuid4()
    chunk_a_id = uuid.uuid4()
    chunk_b_id = uuid.uuid4()

    marker_a = f"MARKER_ALPHA_{uuid.uuid4().hex[:8]}"
    marker_b = f"MARKER_BETA_{uuid.uuid4().hex[:8]}"

    return {
        "user_a_id": user_a_id,
        "user_b_id": user_b_id,
        "doc_a_id": doc_a_id,
        "doc_b_id": doc_b_id,
        "chunk_a_id": chunk_a_id,
        "chunk_b_id": chunk_b_id,
        "marker_a": marker_a,
        "marker_b": marker_b,
    }


@pytest.mark.asyncio
async def test_qdrant_tenant_isolation(tenant_fixture_data):
    """
    Asserts Qdrant vector search strictly isolates tenants and rejects cross-tenant writes.
    """
    d = tenant_fixture_data
    # 1024-dimensional dummy vectors (same dimension as bge-large / modern embedding models)
    dummy_vector_a = [0.1] * 1024
    dummy_vector_b = [0.9] * 1024

    chunk_a = {
        "text": f"Alpha tenant confidential info {d['marker_a']}",
        "meta": {
            "chunk_id": str(d["chunk_a_id"]),
            "doc_id": str(d["doc_a_id"]),
            "user_id": str(d["user_a_id"]),
            "file_name": "alpha.pdf",
            "page_no": 1,
            "headings": "Alpha Heading",
        },
    }

    chunk_b = {
        "text": f"Beta tenant confidential info {d['marker_b']}",
        "meta": {
            "chunk_id": str(d["chunk_b_id"]),
            "doc_id": str(d["doc_b_id"]),
            "user_id": str(d["user_b_id"]),
            "file_name": "beta.pdf",
            "page_no": 1,
            "headings": "Beta Heading",
        },
    }

    # 1. Assert upsert fails when chunk user_id does not match the store function user_id argument
    with pytest.raises(UpsertError):
        await qdrant_upsert([dummy_vector_b], [chunk_b], user_id=d["user_a_id"])

    # 2. Ingest correctly scoped chunks
    await qdrant_upsert([dummy_vector_a], [chunk_a], user_id=d["user_a_id"])
    await qdrant_upsert([dummy_vector_b], [chunk_b], user_id=d["user_b_id"])

    try:
        # 3. User A searches for User B's secret marker -> MUST NOT return User B's chunk
        results_for_a = await vector_search(ChatRequest(query=d["marker_b"]), user_id=d["user_a_id"])
        for r in results_for_a:
            assert d["marker_b"] not in r.get("text", "")
            assert r.get("user_id") == str(d["user_a_id"])

        # 4. User B searches for User A's secret marker -> MUST NOT return User A's chunk
        results_for_b = await vector_search(ChatRequest(query=d["marker_a"]), user_id=d["user_b_id"])
        for r in results_for_b:
            assert d["marker_a"] not in r.get("text", "")
            assert r.get("user_id") == str(d["user_b_id"])

        # 5. Cross-tenant deletion test: User A attempts to delete User B's doc_id
        await qdrant_delete(doc_id=d["doc_b_id"], user_id=d["user_a_id"])

        # User B's document must still be intact
        results_for_b_after = await vector_search(ChatRequest(query=d["marker_b"]), user_id=d["user_b_id"])
        assert any(d["marker_b"] in r.get("text", "") for r in results_for_b_after)

    finally:
        # Cleanup
        await qdrant_delete(doc_id=d["doc_a_id"], user_id=d["user_a_id"])
        await qdrant_delete(doc_id=d["doc_b_id"], user_id=d["user_b_id"])


@pytest.mark.asyncio
async def test_postgres_fts_tenant_isolation(tenant_fixture_data):
    """
    Asserts Postgres full-text search strictly filters by user_id and never leaks cross-tenant chunks.
    """
    d = tenant_fixture_data

    async with AsyncSessionLocal() as session:
        # Setup users
        user_a = User(id=d["user_a_id"], email=f"{d['user_a_id']}@example.com", password_hash="dummy")
        user_b = User(id=d["user_b_id"], email=f"{d['user_b_id']}@example.com", password_hash="dummy")
        session.add_all([user_a, user_b])
        await session.commit()

        # Setup documents
        doc_a = Document(doc_id=d["doc_a_id"], user_id=d["user_a_id"], doc_name="doc_a.pdf")
        doc_b = Document(doc_id=d["doc_b_id"], user_id=d["user_b_id"], doc_name="doc_b.pdf")
        session.add_all([doc_a, doc_b])
        await session.commit()

        # Setup chunks with distinct markers
        chunk_a = Chunk(
            chunk_id=d["chunk_a_id"],
            doc_id=d["doc_a_id"],
            user_id=d["user_a_id"],
            content=f"Confidential data for Alpha tenant containing secret {d['marker_a']}",
            chunk_index=0,
            page_no=1,
            doc_name="doc_a.pdf",
            heading="Alpha",
        )
        chunk_b = Chunk(
            chunk_id=d["chunk_b_id"],
            doc_id=d["doc_b_id"],
            user_id=d["user_b_id"],
            content=f"Confidential data for Beta tenant containing secret {d['marker_b']}",
            chunk_index=0,
            page_no=1,
            doc_name="doc_b.pdf",
            heading="Beta",
        )
        session.add_all([chunk_a, chunk_b])
        await session.commit()

    try:
        async with AsyncSessionLocal() as session:
            # User A searches for marker B
            results_a = await fts_search(ChatRequest(query=d["marker_b"]), user_id=d["user_a_id"], db=session)
            assert len(results_a) == 0, f"Cross-tenant leak: User A received results containing User B data: {results_a}"
            for row in results_a:
                assert row["user_id"] == str(d["user_a_id"])
                assert d["marker_b"] not in row["content"]

            # User B searches for marker A
            results_b = await fts_search(ChatRequest(query=d["marker_a"]), user_id=d["user_b_id"], db=session)
            assert len(results_b) == 0, f"Cross-tenant leak: User B received results containing User A data: {results_b}"
            for row in results_b:
                assert row["user_id"] == str(d["user_b_id"])
                assert d["marker_a"] not in row["content"]

            # User A searches for marker A -> returns chunk A
            results_a_valid = await fts_search(ChatRequest(query=d["marker_a"]), user_id=d["user_a_id"], db=session)
            assert len(results_a_valid) > 0
            assert any(d["marker_a"] in row["content"] for row in results_a_valid)
            assert all(row["user_id"] == str(d["user_a_id"]) for row in results_a_valid)

    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(delete(Chunk).where(Chunk.doc_id.in_([d["doc_a_id"], d["doc_b_id"]])))
            await session.execute(delete(Document).where(Document.doc_id.in_([d["doc_a_id"], d["doc_b_id"]])))
            await session.execute(delete(User).where(User.id.in_([d["user_a_id"], d["user_b_id"]])))
            await session.commit()


@pytest.mark.asyncio
async def test_neo4j_graph_tenant_isolation(tenant_fixture_data):
    """
    Asserts Neo4j enforces user_id on every Document, Entity, and path traversal.
    """
    d = tenant_fixture_data
    entity_a_name = f"EntityA_{d['marker_a']}"
    entity_b_name = f"EntityB_{d['marker_b']}"

    graph_a = GraphExtraction(
        entities=[
            Entity(name=entity_a_name, type="Concept", description="Tenant A concept"),
            Entity(name="SharedCategory", type="Category", description="Tenant A category"),
        ],
        relationships=[
            Relationship(source=entity_a_name, target="SharedCategory", type="BELONGS_TO", description="A to Cat"),
        ],
    )

    graph_b = GraphExtraction(
        entities=[
            Entity(name=entity_b_name, type="Concept", description="Tenant B concept"),
            Entity(name="SharedCategory", type="Category", description="Tenant B category"),
        ],
        relationships=[
            Relationship(source=entity_b_name, target="SharedCategory", type="BELONGS_TO", description="B to Cat"),
        ],
    )

    # Ingest for both users
    await neo4j_client.insert_graph(
        graph=graph_a,
        file_name="doc_a.pdf",
        user_id=d["user_a_id"],
        doc_id=d["doc_a_id"],
    )

    await neo4j_client.insert_graph(
        graph=graph_b,
        file_name="doc_b.pdf",
        user_id=d["user_b_id"],
        doc_id=d["doc_b_id"],
    )

    try:
        async with neo4j_client.driver.session() as session:
            # 1. Verify User A only sees their own document and entities
            res_a = await session.run(
                """
                MATCH (d:Document {user_id: $user_id})-[:MENTIONS]->(e:Entity)-[r:RELATED_TO]->(target:Entity)
                RETURN d.id AS doc_id, e.name AS entity_name, target.name AS target_name, e.user_id AS e_uid, target.user_id AS target_uid
                """,
                user_id=str(d["user_a_id"]),
            )
            records_a = await res_a.data()
            assert len(records_a) > 0
            for rec in records_a:
                assert rec["doc_id"] == str(d["doc_a_id"])
                assert entity_b_name not in rec["entity_name"]
                assert rec["e_uid"] == str(d["user_a_id"])
                assert rec["target_uid"] == str(d["user_a_id"])

            # 2. Verify SharedCategory node is scoped per tenant (no cross-user entity merging)
            res_shared_a = await session.run(
                """
                MATCH (e:Entity {name: 'SharedCategory', user_id: $user_id})
                RETURN e.user_id AS uid
                """,
                user_id=str(d["user_a_id"]),
            )
            shared_records_a = await res_shared_a.data()
            assert len(shared_records_a) == 1
            assert shared_records_a[0]["uid"] == str(d["user_a_id"])

            # 3. Assert User A querying with User B's entity name receives 0 records when scoped
            res_cross = await session.run(
                """
                MATCH (e:Entity {name: $b_entity, user_id: $user_id})
                RETURN e
                """,
                b_entity=entity_b_name,
                user_id=str(d["user_a_id"]),
            )
            cross_records = await res_cross.data()
            assert len(cross_records) == 0

            # 4. Multi-hop traversal test: from User A's document, traverse all paths
            # Assert no node in the returned path has User B's user_id
            res_path = await session.run(
                """
                MATCH path = (d:Document {user_id: $user_id})-[*1..3]-(node)
                RETURN [n IN nodes(path) | n.user_id] AS node_user_ids,
                       [n IN nodes(path) | n.name] AS node_names
                """,
                user_id=str(d["user_a_id"]),
            )
            path_records = await res_path.data()
            for rec in path_records:
                for uid in rec["node_user_ids"]:
                    assert uid == str(d["user_a_id"]), f"Cross-tenant node found in path: {rec}"
                for name in rec["node_names"]:
                    if name:
                        assert entity_b_name not in name

    finally:
        await neo4j_client.delete_graph(doc_id=d["doc_a_id"], user_id=d["user_a_id"])
        await neo4j_client.delete_graph(doc_id=d["doc_b_id"], user_id=d["user_b_id"])


@pytest.mark.asyncio
async def test_end_to_end_retrieval_isolation(tenant_fixture_data):
    """
    Asserts end-to-end hybrid retrieval (retrive) never returns User B's data to User A and vice versa.
    """
    d = tenant_fixture_data

    # Setup DB
    async with AsyncSessionLocal() as session:
        user_a = User(id=d["user_a_id"], email=f"{d['user_a_id']}@example.com", password_hash="dummy")
        user_b = User(id=d["user_b_id"], email=f"{d['user_b_id']}@example.com", password_hash="dummy")
        session.add_all([user_a, user_b])
        doc_a = Document(doc_id=d["doc_a_id"], user_id=d["user_a_id"], doc_name="doc_a.pdf")
        doc_b = Document(doc_id=d["doc_b_id"], user_id=d["user_b_id"], doc_name="doc_b.pdf")
        session.add_all([doc_a, doc_b])
        chunk_a = Chunk(
            chunk_id=d["chunk_a_id"],
            doc_id=d["doc_a_id"],
            user_id=d["user_a_id"],
            content=f"Alpha confidential content {d['marker_a']}",
            chunk_index=0,
            page_no=1,
            doc_name="doc_a.pdf",
            heading="Alpha",
        )
        chunk_b = Chunk(
            chunk_id=d["chunk_b_id"],
            doc_id=d["doc_b_id"],
            user_id=d["user_b_id"],
            content=f"Beta confidential content {d['marker_b']}",
            chunk_index=0,
            page_no=1,
            doc_name="doc_b.pdf",
            heading="Beta",
        )
        session.add_all([chunk_a, chunk_b])
        await session.commit()

    # Setup Qdrant
    vec_a = [0.1] * 1024
    vec_b = [0.9] * 1024
    q_chunk_a = {
        "text": f"Alpha confidential content {d['marker_a']}",
        "meta": {
            "chunk_id": str(d["chunk_a_id"]),
            "doc_id": str(d["doc_a_id"]),
            "user_id": str(d["user_a_id"]),
            "file_name": "doc_a.pdf",
            "page_no": 1,
            "headings": "Alpha",
        },
    }
    q_chunk_b = {
        "text": f"Beta confidential content {d['marker_b']}",
        "meta": {
            "chunk_id": str(d["chunk_b_id"]),
            "doc_id": str(d["doc_b_id"]),
            "user_id": str(d["user_b_id"]),
            "file_name": "doc_b.pdf",
            "page_no": 1,
            "headings": "Beta",
        },
    }
    await qdrant_upsert([vec_a], [q_chunk_a], user_id=d["user_a_id"])
    await qdrant_upsert([vec_b], [q_chunk_b], user_id=d["user_b_id"])

    # Setup Neo4j
    graph_a = GraphExtraction(
        entities=[Entity(name=f"Alpha_{d['marker_a']}", type="Concept")],
        relationships=[],
    )
    graph_b = GraphExtraction(
        entities=[Entity(name=f"Beta_{d['marker_b']}", type="Concept")],
        relationships=[],
    )
    await neo4j_client.insert_graph(graph_a, "doc_a.pdf", d["user_a_id"], d["doc_a_id"])
    await neo4j_client.insert_graph(graph_b, "doc_b.pdf", d["user_b_id"], d["doc_b_id"])

    try:
        async with AsyncSessionLocal() as session:
            # User A calls retrieval searching for User B's secret marker
            from backend.app.services.chat_service import vector_search, fts_search, rrf_fuse, extract_doc_ids

            vec_res, fts_res = await asyncio.gather(
                vector_search(ChatRequest(query=d["marker_b"]), user_id=d["user_a_id"]),
                fts_search(ChatRequest(query=d["marker_b"]), user_id=d["user_a_id"], db=session),
            )
            rrf_res = rrf_fuse(vec_res, fts_res)
            doc_ids = extract_doc_ids(rrf_res, 10)

            # Assert complete isolation
            assert str(d["doc_b_id"]) not in doc_ids
            for item in rrf_res:
                assert item["user_id"] == str(d["user_a_id"])
                assert d["marker_b"] not in item.get("text", "")
                assert d["marker_b"] not in item.get("content", "")

    finally:
        # Cleanup all stores
        await qdrant_delete(doc_id=d["doc_a_id"], user_id=d["user_a_id"])
        await qdrant_delete(doc_id=d["doc_b_id"], user_id=d["user_b_id"])
        await neo4j_client.delete_graph(doc_id=d["doc_a_id"], user_id=d["user_a_id"])
        await neo4j_client.delete_graph(doc_id=d["doc_b_id"], user_id=d["user_b_id"])
        async with AsyncSessionLocal() as session:
            await session.execute(delete(Chunk).where(Chunk.doc_id.in_([d["doc_a_id"], d["doc_b_id"]])))
            await session.execute(delete(Document).where(Document.doc_id.in_([d["doc_a_id"], d["doc_b_id"]])))
            await session.execute(delete(User).where(User.id.in_([d["user_a_id"], d["user_b_id"]])))
            await session.commit()
