"""
Deprecated: GraphSchemaService is no longer required because the knowledge graph
metamodel is static. Use GRAPH_SCHEMA_PROMPT or get_graph_schema_prompt() from
backend.app.graph.schema directly.
"""
from backend.app.graph.schema import (
    GraphSchema,
    get_static_graph_schema,
    GRAPH_SCHEMA_PROMPT,
)


class GraphSchemaService:
    """
    Deprecated: Backward-compatible stub returning the static graph schema
    without connecting to Neo4j or executing dynamic introspection queries.
    """

    def __init__(self):
        self._static_schema = get_static_graph_schema()

    async def get_schema(self, user_id: str | None = None) -> GraphSchema:
        return self._static_schema

    async def invalidate_schema(self, user_id: str) -> None:
        pass

    async def load_schema(self, user_id: str) -> GraphSchema:
        return self._static_schema

    async def close(self) -> None:
        pass
