from qdrant_client import models
from backend.app.database.qdrant import client
import asyncio

async def create_index():
    await client.create_payload_index(
        collection_name="rag-kg",
        field_name="meta.user_id",
        field_schema=models.PayloadSchemaType.UUID,
        wait=True,
    )

    await client.create_payload_index(
            collection_name="rag-kg",
            field_name="meta.doc_id",
            field_schema=models.PayloadSchemaType.UUID,
            wait=True,
        )

if __name__ == "__main__":
    asyncio.run(create_index())