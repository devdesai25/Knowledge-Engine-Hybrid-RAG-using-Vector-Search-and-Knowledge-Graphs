import pytest
from backend.app.graph.schema import (
    GRAPH_SCHEMA_PROMPT,
    get_graph_schema_prompt,
    get_static_graph_schema,
)
from backend.app.graph.schema_service import GraphSchemaService


def test_static_schema_prompt_content():
    prompt = get_graph_schema_prompt()
    assert "(Document)" in prompt
    assert "(Entity)" in prompt
    assert "(Document) - [:MENTIONS] -> (Entity)" in prompt
    assert "(Entity) - [:RELATED_TO] -> (Entity)" in prompt
    assert prompt == GRAPH_SCHEMA_PROMPT


def test_static_graph_schema_model():
    schema = get_static_graph_schema()
    assert len(schema.nodes) == 2
    assert len(schema.relationships) == 2
    assert schema.to_prompt() == GRAPH_SCHEMA_PROMPT


@pytest.mark.asyncio
async def test_deprecated_schema_service_compatibility():
    service = GraphSchemaService()
    schema = await service.get_schema("test-user-id")
    assert schema.to_prompt() == GRAPH_SCHEMA_PROMPT
    await service.invalidate_schema("test-user-id")
    await service.close()
