
import logging
from time import perf_counter

from backend.app.settings import setting
from backend.app.embedder.embedding import generate_embedding
from backend.app.database.qdrant import client
from backend.app.schema.chat import ChatRequest
from backend.app.llm.client import LLMClient

logger = logging.getLogger(__name__)

async def retrive(query: ChatRequest):
    start = perf_counter()

    query_embed = generate_embedding(query.query)

    chunks = await client.query_points(
        "rag-kg",
        query=query_embed
    )

#    print(chunks)
#    print(chunks.points[0])
#    print(chunks.points[0].score)
#    print(chunks.points[0].payload)
#    print(chunks.points[0].payload['meta'])

    response = LLMClient().generate(query.query, chunks)

    print(response)
    elapsed = perf_counter() - start

    logger.info(
        "Processed query | time: %.2fs",
        elapsed
    )

    return response