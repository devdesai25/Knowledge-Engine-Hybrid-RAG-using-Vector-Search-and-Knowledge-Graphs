import asyncio
import json
import logging
import random
from time import perf_counter
from openai import (
    AsyncOpenAI,
    APIError,
    APIConnectionError,
    RateLimitError,
    InternalServerError,
)
from .config import GenerationConfig as AppGenerationConfig

from backend.app.settings import setting
from backend.app.schema.graph import GraphExtraction, Entity, Relationship
from backend.app.core.exceptions.exceptions import GenerationError, LLMTimeoutError

logger = logging.getLogger(__name__)

CHUNK_BATCH_SIZE = 3
MAX_CONCURRENT_BATCHES = 4

# Module-level semaphore shared across all concurrent uploads
_GLOBAL_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_BATCHES)


class LLMExtraction:

    def __init__(self, config: AppGenerationConfig | None = None):
        self._config = config or AppGenerationConfig()
        # SDK default retries disabled to prevent rapid retry storms; retries handled in _call()
        self._client = AsyncOpenAI(
            api_key=setting.deepseek_api_key.get_secret_value(),
            base_url="https://api.deepseek.com",
            timeout=90.0,
            max_retries=0,
        )
        self._semaphore = _GLOBAL_SEMAPHORE

    def _build_prompt(self) -> str:
        output_schema = json.dumps(GraphExtraction.model_json_schema())
        return f"""
            You are a knowledge graph extraction system. Extract a structured knowledge graph from the provided text chunk (part of a larger document).
            
            =============ENTITIES=============
            Extract meaningful entities explicitly mentioned in the text — e.g. People, Organizations, Locations, Technologies, Products, Concepts, Events, Methods, Diseases, Documents, or other domain-specific types.
            
            For each entity:
            - name: canonical name as it appears in the text
            - type: concise semantic type (e.g. Person, Organization, Technology, Concept, Event)
            - description: brief, based only on what the text states. Keep every description under 15 words.
            
            Skip generic nouns, pronouns, and trivial phrases. If the chunk has no meaningful entities, return an empty list.
            
            =============RELATIONSHIPS=============
            Extract a relationship only when the text provides explicit evidence for it — not just co-occurrence in the same sentence/paragraph.
            
            For each relationship:
            - source: source entity name
            - target: target entity name
            - type: concise semantic type (e.g. WORKS_FOR, LOCATED_IN, USES, PRODUCES, DEVELOPED_BY, PART_OF, CAUSED_BY, RELATED_TO)
            - description: brief, based only on the text. Keep every description under 15 words.
            
            Keep direction meaningful (e.g. "Google developed TensorFlow" -> source: Google, target: TensorFlow). Prefer specific relationship types over generic ones when the text supports it.
            
            =============CONSISTENCY & GROUNDING=============
            - Use the same entity name consistently across multiple mentions/relationships; don't merge distinct entities just because names are similar.
            - Use only information stated in the text — no outside knowledge, no inferred properties, causes, identities, or relationships.
            - If something is ambiguous or the chunk is cut off mid-thought, leave it unextracted rather than guessing.
            - Keep every description under 15 words.
            
            =============EXAMPLE=============
            Text: "OpenAI released GPT-4 in 2023. The model was trained using reinforcement learning from human feedback (RLHF)."
            
            Output:
            {{
              "entities": [
                {{"name": "OpenAI", "type": "Organization", "description": "Released GPT-4 in 2023."}},
                {{"name": "GPT-4", "type": "Product", "description": "A model released by OpenAI in 2023."}},
                {{"name": "RLHF", "type": "Method", "description": "Technique used to train GPT-4."}}
              ],
              "relationships": [
                {{"source": "OpenAI", "target": "GPT-4", "type": "DEVELOPED_BY", "description": "OpenAI released GPT-4 in 2023."}},
                {{"source": "GPT-4", "target": "RLHF", "type": "USES", "description": "GPT-4 was trained using RLHF."}}
              ]
            }}
            
            =============OUTPUT=============
            Return only valid JSON matching this schema — no explanations or extra text:
            {output_schema}
        """

    async def _call(self, messages: list[dict], max_attempts: int = 5) -> str:
        """
        Executes a chat completion call with up to 5 attempts, exponential backoff with jitter
        on transient connection, rate limit, and internal server errors.
        Must be called inside the semaphore block.
        """
        for attempt in range(max_attempts):
            t0 = perf_counter()
            try:
                response = await self._client.chat.completions.create(
                    model=self._config.model,
                    max_tokens=self._config.max_output_tokens,
                    temperature=self._config.temperature,
                    messages=messages,
                    response_format={"type": "json_object"},
                    extra_body={"thinking": {"type": "disabled"}},
                    timeout=90.0,
                )
                duration = perf_counter() - t0
                choice = response.choices[0]
                finish_reason = choice.finish_reason
                completion_tokens = response.usage.completion_tokens if response.usage else None

                logger.info(
                    "DeepSeek LLM call: duration=%.2fs, completion_tokens=%s, finish_reason=%s",
                    duration,
                    completion_tokens,
                    finish_reason,
                )

                if finish_reason == "length":
                    raise ValueError("LLM response truncated due to length (finish_reason='length')")

                content = choice.message.content
                if not content:
                    raise ValueError("Empty response received from DeepSeek LLM")
                return content

            except (APIConnectionError, RateLimitError, InternalServerError) as e:
                duration = perf_counter() - t0
                if attempt < max_attempts - 1:
                    sleep_time = min(30.0, 2.0 ** attempt) + random.uniform(0.1, 1.0)
                    logger.warning(
                        "DeepSeek call attempt %d/%d encountered %s (took %.2fs). Retrying in %.2fs...",
                        attempt + 1,
                        max_attempts,
                        type(e).__name__,
                        duration,
                        sleep_time,
                    )
                    await asyncio.sleep(sleep_time)
                else:
                    logger.error(
                        "DeepSeek call failed after %d attempts: %s",
                        max_attempts,
                        e,
                    )
                    raise

    async def _extract_with_split(
        self,
        chunk_list: list[str],
        failed_chunks: list[str] | None = None,
    ) -> GraphExtraction:
        """
        Extracts knowledge graph from a list of text chunks.
        On ValueError (including Pydantic ValidationError and finish_reason='length')
        or APIError, recursively splits chunk_list in half and retries each half.
        If a single chunk still fails, logs and skips it.
        The semaphore is held ONLY around the API call, not around the recursion.
        """
        if not chunk_list:
            return GraphExtraction(entities=[], relationships=[])

        batch_text = "\n\n".join(chunk_list)
        messages = [
            {"role": "system", "content": self._build_prompt()},
            {"role": "user", "content": batch_text},
        ]

        try:
            # Hold semaphore ONLY around the API call
            async with self._semaphore:
                output_json = await self._call(messages)

            return GraphExtraction.model_validate_json(output_json)

        except (ValueError, APIError) as e:
            if len(chunk_list) > 1:
                mid = len(chunk_list) // 2
                logger.warning(
                    "Extraction failed for batch of %d chunks (%s: %s). Splitting into %d and %d chunks...",
                    len(chunk_list),
                    type(e).__name__,
                    e,
                    mid,
                    len(chunk_list) - mid,
                )
                # Recursion executes outside the semaphore block
                left_graph = await self._extract_with_split(chunk_list[:mid], failed_chunks)
                right_graph = await self._extract_with_split(chunk_list[mid:], failed_chunks)
                return self._merge_graphs([left_graph, right_graph])
            else:
                logger.warning(
                    "Extraction failed for single chunk (%s: %s). Skipping chunk.",
                    type(e).__name__,
                    e,
                )
                if failed_chunks is not None:
                    failed_chunks.append(chunk_list[0])
                return GraphExtraction(entities=[], relationships=[])

    @staticmethod
    def _merge_graphs(graphs: list[GraphExtraction]) -> GraphExtraction:
        entity_map: dict[str, Entity] = {}
        for g in graphs:
            for ent in g.entities:
                key = ent.name.strip().lower()
                if not key:
                    continue
                if key not in entity_map:
                    entity_map[key] = ent
                else:
                    existing = entity_map[key]
                    best_name = ent.name if (ent.name and ent.name[0].isupper() and not existing.name[0].isupper()) else existing.name
                    best_desc = ent.description if (ent.description and len(ent.description) > len(existing.description or "")) else existing.description
                    best_type = ent.type if (ent.type and ent.type != "Concept") else existing.type
                    entity_map[key] = Entity(name=best_name, type=best_type, description=best_desc)

        rel_map: dict[tuple[str, str, str], Relationship] = {}
        for g in graphs:
            for rel in g.relationships:
                key = (rel.source.strip().lower(), rel.target.strip().lower(), rel.type.strip().upper())
                if not key[0] or not key[1]:
                    continue
                if key not in rel_map:
                    rel_map[key] = rel
                else:
                    existing = rel_map[key]
                    best_desc = rel.description if (rel.description and len(rel.description) > len(existing.description or "")) else existing.description
                    rel_map[key] = Relationship(
                        source=existing.source,
                        target=existing.target,
                        type=existing.type,
                        description=best_desc
                    )

        return GraphExtraction(
            entities=list(entity_map.values()),
            relationships=list(rel_map.values())
        )

    async def generate_structure(self, chunks: list[str]) -> GraphExtraction:
        if not chunks:
            return GraphExtraction(entities=[], relationships=[])

        # Partition chunks into initial batches of CHUNK_BATCH_SIZE (3)
        batches = [
            chunks[i:i + CHUNK_BATCH_SIZE]
            for i in range(0, len(chunks), CHUNK_BATCH_SIZE)
        ]
        total_batches = len(batches)

        async def _process_batch(batch_chunks: list[str]) -> tuple[GraphExtraction, bool]:
            failed_chunks: list[str] = []
            try:
                graph = await self._extract_with_split(batch_chunks, failed_chunks)
                # Batch is considered failed if all chunks in it failed
                batch_failed = (len(failed_chunks) == len(batch_chunks))
                return graph, batch_failed
            except Exception as e:
                logger.error("Unexpected error in batch extraction: %s", e)
                return GraphExtraction(entities=[], relationships=[]), True

        tasks = [_process_batch(batch) for batch in batches]
        results = await asyncio.gather(*tasks)

        successful_graphs: list[GraphExtraction] = []
        failed_batches = 0

        for graph, batch_failed in results:
            if batch_failed:
                failed_batches += 1
            if graph.entities or graph.relationships:
                successful_graphs.append(graph)

        failure_rate = failed_batches / total_batches if total_batches > 0 else 0.0
        logger.info(
            "Graph extraction complete: %d/%d batches succeeded, %d failed (failure rate: %.1f%%)",
            total_batches - failed_batches,
            total_batches,
            failed_batches,
            failure_rate * 100,
        )

        if failure_rate > 0.20:
            raise GenerationError(
                f"Graph extraction failed: {failed_batches}/{total_batches} batches "
                f"({failure_rate:.1%}) failed, exceeding the 20% failure threshold."
            )

        if not successful_graphs:
            return GraphExtraction(entities=[], relationships=[])

        return self._merge_graphs(successful_graphs)


llm_extraction = LLMExtraction()
