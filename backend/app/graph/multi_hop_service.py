import json
import logging
from time import perf_counter
from uuid import UUID
from typing import Any

from openai import AsyncOpenAI, APIStatusError, APITimeoutError
from backend.app.settings import setting
from backend.app.database.neo4j import neo4j_client
from backend.app.schema.chat import MultiHopDecision
from backend.app.schema.retreival import GraphQuery
from backend.app.graph.schema import GRAPH_SCHEMA_PROMPT
from backend.app.core.exceptions.exceptions import LLMTimeoutError

logger = logging.getLogger(__name__)

FORBIDDEN_KEYWORDS = {
    "CREATE", "MERGE", "DELETE", "SET", "REMOVE",
    "CALL", "LOAD CSV", "DROP", "ALTER", "FOREACH",
    "DETACH", "GRANT", "DENY", "REVOKE",
}

def deduplicate_records(records: list[Any]) -> list[dict[str, Any]]:
    """Deduplicates Neo4j records based on canonical JSON serialization."""
    seen = set()
    unique: list[dict[str, Any]] = []
    for r in records:
        d = r.data() if hasattr(r, "data") else dict(r)
        serialized = json.dumps(d, sort_keys=True, default=str)
        if serialized not in seen:
            seen.add(serialized)
            unique.append(d)
    return unique


class MultiHopGraphService:
    """
    Independent multi-hop Knowledge Graph search engine:
    1. Untied from vector/FTS candidate_doc_ids: operates across the tenant's entire graph.
    2. Hop 1: Generates and executes an initial seed Cypher query matching entities/concepts.
    3. Hop 2: Reflects on the returned graph records to determine if relational bridges
              (e.g., A -> B -> C) are missing and generates a targeted follow-up query.
    4. Merges and de-duplicates all retrieved graph subgraphs.
    """

    def __init__(self, model_name: str | None = None):
        from backend.app.llm.config import GenerationConfig
        self._config = GenerationConfig()
        if model_name:
            self._config.model = model_name
        self._client = AsyncOpenAI(
            api_key=setting.deepseek_api_key.get_secret_value(),
            base_url="https://api.deepseek.com",
            max_retries=1,
            timeout=30.0,
        )

    def validate_cypher(self, graph_query: str) -> str:
        cleaned = graph_query.strip().rstrip(";")
        normalized = cleaned.upper()

        words = set(normalized.split())
        for keyword in FORBIDDEN_KEYWORDS:
            if keyword in words:
                raise ValueError(f"Forbidden keyword found: {keyword}")

        if "$USER_ID" not in normalized:
            raise ValueError("Query must filter by $user_id.")

        if "LIMIT" not in normalized:
            cleaned += " LIMIT 20"

        return cleaned

    @staticmethod
    def normalize_parameters(cypher: str, parameters: dict[str, Any]) -> dict[str, Any]:
        """Ensures parameters expected as lists by Cypher (e.g. IN $param) are actual lists."""
        normalized = dict(parameters)
        upper_cypher = cypher.upper()
        for k, v in list(normalized.items()):
            if isinstance(v, str) and v.strip().startswith("[") and v.strip().endswith("]"):
                try:
                    v = json.loads(v)
                    normalized[k] = v
                except Exception:
                    pass
            target_pattern = f"${k.upper()}"
            if target_pattern in upper_cypher and "IN" in upper_cypher:
                if f"IN {target_pattern}" in upper_cypher or f"IN({target_pattern}" in upper_cypher:
                    if not isinstance(v, (list, tuple, set)):
                        normalized[k] = [v] if v is not None else []
        return normalized

    async def execute_cypher(self, cypher: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        """Executes a validated read-only Cypher query with parameters against Neo4j."""
        validated_cypher = self.validate_cypher(cypher)
        norm_params = self.normalize_parameters(validated_cypher, parameters)
        async with neo4j_client.driver.session() as session:
            result = await session.run(validated_cypher, **norm_params)
            data = await result.data()
            return data

    async def generate_initial_query(
        self, 
        user_query: str, 
        schema_prompt: str,
        attempt: int = 0
    ) -> GraphQuery:
        """Generates the Hop 1 seed Cypher query without document restrictions."""
        if attempt >= 2:
            raise ValueError("Failed to generate a valid Cypher query after retries.")

        schema_json = json.dumps(GraphQuery.model_json_schema(), indent=2)

        graph_system_instruction = f"""
            ========== System Instructions ==========
            You are an expert Neo4j Cypher query generator for a hybrid RAG system.
            Generate a read-only Cypher query to retrieve seed entities, concepts, and their direct 
            relationships relevant to the user's question.

            RULES:
            - Query data belonging ONLY to $user_id.
            - Do NOT restrict queries to specific candidate document IDs unless the question explicitly asks for a specific filename.
            - Search across the tenant's global graph of entities and relationships.
            - Use ONLY the labels, properties, and relationship types present in the schema:
              (:Entity {{name, type, description, user_id}})
              (:Entity)-[:RELATED_TO {{type, description}}]->(:Entity)
              (:Document {{id, filename, user_id}})-[:MENTIONS]->(:Entity)
            - Extract search terms (e.g. entity names) into the parameters array.
            - End the Cypher query with LIMIT 20.

            ========== Neo4j Schema ==========
            {schema_prompt}

            ========== Output Instructions ==========
            Respond ONLY with a valid JSON matching this schema:
            {schema_json}
        """

        try:
            response = await self._client.chat.completions.create(
                model=self._config.model,
                max_tokens=1500,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": graph_system_instruction},
                    {"role": "user", "content": user_query}
                ],
                response_format={"type": "json_object"},
                extra_body={"thinking": {"type": "disabled"}},
                timeout=30.0,
            )
            output_json = response.choices[0].message.content
            graph_query_obj = GraphQuery.model_validate_json(output_json)
            graph_query_obj.query = self.validate_cypher(graph_query_obj.query)
            return graph_query_obj

        except ValueError as e:
            logger.warning("Cypher query validation error on attempt %d: %s. Retrying...", attempt + 1, e)
            retry_prompt = f"{user_query}\n\n[Correction needed: The previous query failed validation: {e}. Please ensure it includes $user_id and avoids forbidden keywords.]"
            return await self.generate_initial_query(retry_prompt, schema_prompt, attempt + 1)
        except (APITimeoutError, TimeoutError, APIStatusError) as e:
            if attempt < 1:
                logger.warning("DeepSeek query generation returned %s. Retrying once...", e)
                return await self.generate_initial_query(user_query, schema_prompt, attempt + 1)
            raise LLMTimeoutError(f"DeepSeek request failed: {e}") from e

    async def reflect_and_expand(
        self,
        user_query: str,
        schema_prompt: str,
        hop_1_records: list[dict[str, Any]],
        user_id: UUID,
    ) -> MultiHopDecision:
        """
        Hop 2 Reflection:
        Analyzes records retrieved in Hop 1. If an intermediate entity was discovered
        or a missing relational link exists (e.g., Joint Board -> State Board found, but
        need State Board -> Central Board), generates a targeted follow-up Cypher query.
        """
        schema_json = json.dumps(MultiHopDecision.model_json_schema(), indent=2)

        reflection_system = f"""
            ========== Multi-Hop Graph Reasoner ==========
            You are a multi-hop reasoning agent inspecting evidence retrieved from a Neo4j knowledge graph.

            Your goal is to inspect what was found in Hop 1 and decide:
            1. Does the retrieved evidence completely satisfy the relational requirements of the question?
               If YES: set `is_complete` = true and `next_cypher_query` = null.
            2. Is there a missing relational bridge or multi-hop path?
               For example:
               - The question asks about Entity A's relationship to Entity C.
               - Hop 1 revealed that Entity A is related to Entity B (e.g., A is 'TREATED_AS' B).
               - Now we MUST hop from Entity B to Entity C to complete the chain!
               If NO (missing link): set `is_complete` = false, describe your reasoning, and write the 
               exact targeted read-only Cypher query for the next hop.

            CRITICAL CYPHER RULES:
            - Must filter by $user_id.
            - Must end with LIMIT 20.
            - Do NOT repeat the exact query from Hop 1; focus on traversing the new frontier/bridge nodes.

            ========== Schema ==========
            {schema_prompt}

            ========== Output Schema ==========
            Respond ONLY with a valid JSON matching:
            {schema_json}
        """

        user_content = f"""
        User Question:
        {user_query}

        Hop 1 Retrieved Evidence:
        {json.dumps(hop_1_records[:15], indent=2, default=str)}
        """

        try:
            response = await self._client.chat.completions.create(
                model=self._config.model,
                max_tokens=1500,
                temperature=0.1,
                messages=[
                    {"role": "system", "content": reflection_system},
                    {"role": "user", "content": user_content}
                ],
                response_format={"type": "json_object"},
                extra_body={"thinking": {"type": "disabled"}},
                timeout=25.0,
            )
            output_json = response.choices[0].message.content
            decision = MultiHopDecision.model_validate_json(output_json)
            if decision.next_cypher_query:
                decision.next_cypher_query = self.validate_cypher(decision.next_cypher_query)
            return decision

        except Exception as e:
            logger.warning("[Multi-Hop Reflection Error]: %s. Terminating after Hop 1.", e)
            return MultiHopDecision(
                is_complete=True,
                reasoning=f"Reflection encountered error: {e}. Defaulting to Hop 1 results.",
                next_cypher_query=None,
                parameters={}
            )

    async def search(
        self,
        query_text: str,
        user_id: UUID,
        context_doc_id: list[UUID] | None = None,
        max_hops: int = 2,
    ) -> list[dict[str, Any]]:
        """
        Executes an independent iterative multi-hop Knowledge Graph search.
        """
        t0 = perf_counter()
        schema_prompt = GRAPH_SCHEMA_PROMPT

        # -------------------------------------------------------------
        # HOP 1: Initial Seed Cypher Query (Untied from Candidate Doc IDs)
        # -------------------------------------------------------------
        t_hop1_start = perf_counter()
        try:
            query_obj = await self.generate_initial_query(query_text, schema_prompt)
            parameters = {p.name: p.value for p in query_obj.parameters}
            parameters["user_id"] = str(user_id)
            if context_doc_id:
                parameters["candidate_doc_ids"] = [str(d) for d in context_doc_id]
            else:
                parameters["candidate_doc_ids"] = []

            hop1_records = await self.execute_cypher(query_obj.query, parameters)
        except Exception as e:
            logger.warning("[Multi-Hop Graph] Hop 1 generation/execution failed: %s", e)
            hop1_records = []

        t_hop1 = perf_counter() - t_hop1_start
        logger.info("[TIMING] graph_search Hop 1: %.3fs (records: %d)", t_hop1, len(hop1_records))

        if not hop1_records or max_hops <= 1:
            total_time = perf_counter() - t0
            logger.info("[TIMING] graph_search total: %.3fs (1 hop completed)", total_time)
            return deduplicate_records(hop1_records)

        # -------------------------------------------------------------
        # HOP 2: Reflection & Bridge Expansion
        # -------------------------------------------------------------
        t_hop2_start = perf_counter()
        accumulated_records = list(hop1_records)

        try:
            decision = await self.reflect_and_expand(
                user_query=query_text,
                schema_prompt=schema_prompt,
                hop_1_records=hop1_records,
                user_id=user_id,
            )
            logger.info(
                "[Multi-Hop Graph] Hop 2 Decision: complete=%s, reasoning=%s",
                decision.is_complete,
                decision.reasoning,
            )

            if not decision.is_complete and decision.next_cypher_query:
                params = decision.parameters or {}
                params["user_id"] = str(user_id)
                if "candidate_doc_ids" not in params:
                    params["candidate_doc_ids"] = [str(d) for d in (context_doc_id or [])]

                hop2_records = await self.execute_cypher(decision.next_cypher_query, params)
                logger.info("[Multi-Hop Graph] Hop 2 retrieved %d new records.", len(hop2_records))
                accumulated_records.extend(hop2_records)

        except Exception as e:
            logger.warning("[Multi-Hop Graph] Hop 2 expansion encountered error: %s", e)

        t_hop2 = perf_counter() - t_hop2_start
        total_time = perf_counter() - t0

        final_records = deduplicate_records(accumulated_records)
        logger.info(
            "[TIMING] graph_search total: %.3fs (Hop 1: %.3fs, Hop 2: %.3fs, total_unique_records: %d)",
            total_time,
            t_hop1,
            t_hop2,
            len(final_records),
        )
        return final_records
