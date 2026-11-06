import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from openai import InternalServerError, RateLimitError, APIConnectionError
from docling.chunking import HybridChunker

from backend.app.schema.graph import GraphExtraction, Entity, Relationship
from backend.app.core.exceptions.exceptions import GenerationError
from backend.app.llm.client_er import LLMExtraction, CHUNK_BATCH_SIZE, MAX_CONCURRENT_BATCHES
from backend.app.chunker.docling import _chunker
from backend.app.lifespan_method import lifespan
from neo4j.exceptions import ServiceUnavailable, SessionExpired


def test_chunker_max_tokens_capped():
    """Verify docling chunker is capped at 400 tokens."""
    assert _chunker.tokenizer.max_tokens == 400
    assert _chunker.tokenizer.get_max_tokens() == 400


@pytest.mark.asyncio
async def test_llm_call_retries_and_succeeds():
    """Verify _call retries on transient errors with exponential backoff and succeeds."""
    extractor = LLMExtraction()
    
    mock_choice = MagicMock()
    mock_choice.finish_reason = "stop"
    mock_choice.message.content = '{"entities": [], "relationships": []}'
    
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.completion_tokens = 42

    call_count = 0

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise InternalServerError("Service temporarily busy", response=MagicMock(status_code=500), body={})
        return mock_response

    with patch.object(extractor._client.chat.completions, "create", side_effect=mock_create):
        async with extractor._semaphore:
            content = await extractor._call([{"role": "user", "content": "test"}])
        assert content == '{"entities": [], "relationships": []}'
        assert call_count == 3


@pytest.mark.asyncio
async def test_llm_call_length_finish_reason_raises_value_error():
    """Verify choices[0].finish_reason == 'length' raises ValueError to trigger split."""
    extractor = LLMExtraction()

    mock_choice = MagicMock()
    mock_choice.finish_reason = "length"
    mock_choice.message.content = '{"entities": [{"name": "Incomp'
    
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.completion_tokens = 5120

    with patch.object(extractor._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
        with pytest.raises(ValueError, match="truncated due to length"):
            async with extractor._semaphore:
                await extractor._call([{"role": "user", "content": "test"}])


@pytest.mark.asyncio
async def test_extract_with_split_recurses_on_failure():
    """Verify _extract_with_split splits multi-chunk batch on ValueError/APIError and merges halves."""
    extractor = LLMExtraction()

    # Suppose a 2-chunk batch fails when combined, but succeeds for individual chunks
    chunk_1 = "Chunk 1: Apple was founded by Steve Jobs."
    chunk_2 = "Chunk 2: Microsoft was founded by Bill Gates."

    g1 = GraphExtraction(
        entities=[Entity(name="Apple", type="Organization", description="Tech company")],
        relationships=[]
    )
    g2 = GraphExtraction(
        entities=[Entity(name="Microsoft", type="Organization", description="Software company")],
        relationships=[]
    )

    call_index = 0

    async def mock_call(messages, **kwargs):
        nonlocal call_index
        call_index += 1
        prompt_content = messages[-1]["content"]
        if chunk_1 in prompt_content and chunk_2 in prompt_content:
            # Combined fails due to length or JSON error
            raise ValueError("Too long for single call")
        elif chunk_1 in prompt_content:
            return g1.model_dump_json()
        elif chunk_2 in prompt_content:
            return g2.model_dump_json()
        return '{"entities": [], "relationships": []}'

    with patch.object(extractor, "_call", side_effect=mock_call):
        merged = await extractor._extract_with_split([chunk_1, chunk_2])
        names = {e.name for e in merged.entities}
        assert "Apple" in names
        assert "Microsoft" in names


@pytest.mark.asyncio
async def test_generate_structure_raises_when_failure_rate_exceeds_20_percent():
    """Verify generate_structure raises GenerationError when more than 20% of batches fail."""
    extractor = LLMExtraction()

    chunks = [f"Chunk {i}" for i in range(12)]  # 4 batches of 3 chunks

    batch_idx = 0

    async def mock_extract(batch_chunks, failed_chunks=None):
        nonlocal batch_idx
        batch_idx += 1
        # Fail 2 out of 4 batches (50% failure rate > 20%)
        if batch_idx in (1, 2):
            if failed_chunks is not None:
                failed_chunks.extend(batch_chunks)
            return GraphExtraction(entities=[], relationships=[])
        return GraphExtraction(
            entities=[Entity(name=f"Entity_{batch_idx}", type="Concept", description="desc")],
            relationships=[]
        )

    with patch.object(extractor, "_extract_with_split", side_effect=mock_extract):
        with pytest.raises(GenerationError, match="exceeding the 20% failure threshold"):
            await extractor.generate_structure(chunks)


@pytest.mark.asyncio
async def test_lifespan_teardown_hasattr_guard():
    """Verify lifespan teardown safely checks hasattr without raising AttributeError."""
    app = MagicMock()
    app.state = MagicMock(spec=[])  # Empty state without attributes

    async with lifespan(app):
        pass  # Entering and exiting lifespan should clean up without error
