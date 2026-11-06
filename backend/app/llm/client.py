import json
import logging
from openai import AsyncOpenAI, LengthFinishReasonError, APIStatusError

from backend.app.settings import setting
from backend.app.core.exceptions.exceptions import GenerationError, LLMTimeoutError, LLMLengthFinishError
from backend.app.llm.config import GenerationConfig as AppGenerationConfig
from backend.app.llm.format import format_chunk
from backend.app.schema.retreival import GraphQuery
from backend.app.database.neo4j import neo4j_client

logger = logging.getLogger(__name__)

FORBIDDEN_KEYWORDS = {
    "CREATE", "MERGE", "DELETE", "SET", "REMOVE",
    "CALL", "LOAD CSV", "DROP", "ALTER", "FOREACH",
    "DETACH", "GRANT", "DENY", "REVOKE",
}

class LLMClient:

    def __init__(self, config: AppGenerationConfig | None = None):
        self._config = config or AppGenerationConfig()
        self._client = AsyncOpenAI(
            api_key=setting.deepseek_api_key.get_secret_value(),
            base_url="https://api.deepseek.com",
            max_retries=1,
            timeout=30.0,
        )

    async def generate(self, query: str, context_chunks, graph_result) -> str:
        chunk_texts = [
            format_chunk(
                chunk.get("text") or chunk.get("content", ""),
                chunk.get("page_no", 1),
                chunk.get("headings") or chunk.get("heading", ""),
            )
            for chunk in context_chunks
        ]
        
        # graph context — flatten each Neo4j record into a readable line
        graph_texts = []
        for record in graph_result:
            data = record.data() if hasattr(record, "data") else dict(record)
            line = ", ".join(f"{k}: {v}" for k, v in data.items())
            graph_texts.append(line)

        context_block = "\n\n--\n\n".join(chunk_texts + graph_texts)
        prompt = f"Context: \n{context_block}\n\nQuestion:\n{query}"

        system_instruction = (
            "You are an enterprise document assistant. Answer questions using "
            "only the provided context excerpts from company PDF documents. "
            "Cite the source document and page number when available. "
            "If the context does not contain enough information to answer "
            "confidently, say so explicitly rather than speculating. "
            "Do not reveal information from outside the provided context, "
            "even if you know it from general knowledge."
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._config.model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt},
                ],
                timeout=45.0,
            )
        except TimeoutError as e:
            raise LLMTimeoutError(f"LLM request timed out: {e}") from e

        text = response.choices[0].message.content
        if not text:
            raise GenerationError("LLM returned empty response")

        return text

    async def generate_graph_query(self, query: str, schema=None, attempt: int = 0):
        # Limit to 2 attempts max to avoid recursive retry loops
        if attempt >= 2:
            raise GenerationError("Failed to generate a valid Cypher query after retries.")

        if schema is None:
            from backend.app.graph.schema import GRAPH_SCHEMA_PROMPT
            schema = GRAPH_SCHEMA_PROMPT
        elif hasattr(schema, "to_prompt"):
            schema = schema.to_prompt()

        schema_json = json.dumps(GraphQuery.model_json_schema(), indent=2)

        graph_system_instruction = f"""
            ========== System Instructions ==========

            You are a Cypher query generator.

            You are given a user's natural language question and the available
            Neo4j graph schema.

            Generate a read-only Cypher query that retrieves the information
            necessary to answer the question.

            Use parameters rather than interpolating user values directly.

            Use ONLY the labels, properties, relationship types, and relationship
            directions present in the schema.

            Do not modify the database.

            Do NOT invent:
            - labels
            - properties
            - relationship types
            - relationship directions

            The query must only access data belonging to the authenticated user ($user_id).

            ========== Neo4j Schema ==========

            {schema}

            ========== Parameter Extraction Rules ==========

            Extract the actual values from the user's question and put them into
            the `parameters` array.

            Parameter values must contain ONLY the actual value, not the words
            used to describe that value.

            ========== Output Instructions ==========

            Respond ONLY with a valid JSON object matching this schema:
            {schema_json}

            Every generated cypher query must end with "LIMIT 20".

            ========== Graph Semantics ==========

            Entities and relationships form the primary semantic network:
            (:Entity {name, type, description, user_id})
            (:Entity)-[:RELATED_TO {type, description}]->(:Entity)
            (:Document {id, filename, user_id})-[:MENTIONS]->(:Entity)

            Do NOT restrict queries to candidate document IDs unless the question explicitly asks 
            for a specific document filename. Traverse entities globally across the tenant ($user_id).

            ========== Reserved Parameters ==========

            `user_id` and `candidate_doc_ids` are provided by the system at
            execution time. Do NOT include them in the `parameters` array —
            only reference them in your Cypher as $user_id and
            $candidate_doc_ids.
        """

        try:
            response = await self._client.chat.completions.create(
                model=self._config.model,
                max_tokens=1500,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": graph_system_instruction},
                    {"role": "user", "content": query}
                ],
                response_format={"type": "json_object"},
                extra_body={"thinking": {"type": "disabled"}},
                timeout=30.0,
            )
            output_json = response.choices[0].message.content
            graph_query_obj = GraphQuery.model_validate_json(output_json)

            try:
                # Sanitize and validate (auto-fixes missing LIMIT and trailing semicolons)
                graph_query_obj.query = self.validate_cypher(graph_query_obj.query)
            except ValueError as e:
                logger.warning(
                    "Cypher query validation error on attempt %d: %s. Retrying with feedback...",
                    attempt + 1, e
                )
                retry_prompt = f"{query}\n\n[Correction needed: The previous query failed validation: {e}. Please ensure it includes $user_id and avoids forbidden keywords.]"
                return await self.generate_graph_query(retry_prompt, schema, attempt + 1)

            return graph_query_obj

        except (TimeoutError, APIStatusError) as e:
            if attempt < 1:
                logger.warning("DeepSeek query generation returned %s. Retrying once...", e)
                return await self.generate_graph_query(query, schema, attempt + 1)
            raise LLMTimeoutError(f"DeepSeek request failed: {e}") from e
        except LengthFinishReasonError as e:
            raise LLMLengthFinishError(f"DeepSeek response length exceeded: {e}") from e

    async def generate_graph_result(self, response, user_id, candidate_doc_ids=None):
        parameters = {
            parameter.name: parameter.value
            for parameter in response.parameters
        }
        parameters["user_id"] = str(user_id)
        parameters["candidate_doc_ids"] = list(dict.fromkeys(candidate_doc_ids or []))

        async with neo4j_client.driver.session() as session:
            answer = await session.run(response.query, **parameters)
            records = await answer.data()

        return records

    @staticmethod
    def validate_cypher(graph_query: str) -> str:
        cleaned = graph_query.strip().rstrip(";")
        normalized = cleaned.upper()

        words = set(normalized.split())
        for keyword in FORBIDDEN_KEYWORDS:
            if keyword in words:
                raise ValueError(f"Forbidden keyword found: {keyword}")

        if "$USER_ID" not in normalized:
            raise ValueError("Query must filter by $user_id.")

        # Auto-append LIMIT 20 if missing, instead of failing validation
        if "LIMIT" not in normalized:
            cleaned += " LIMIT 20"

        return cleaned
