from pydantic import BaseModel, Field

GRAPH_SCHEMA_PROMPT = """# Neo4j Graph Schema

Use ONLY the labels, properties, relationship types, and relationship directions defined below.
Do NOT invent labels, properties, or relationship types.

# Nodes
(Document)
 - filename: String
 - id: String
 - user_id: String
(Entity)
 - description: String
 - name: String
 - type: String
 - user_id: String

# Relationships
(Document) - [:MENTIONS] -> (Entity)
(Entity) - [:RELATED_TO] -> (Entity)
 - description: String
 - type: String"""


def get_graph_schema_prompt() -> str:
    """Returns the static Neo4j schema prompt for Cypher generation."""
    return GRAPH_SCHEMA_PROMPT


class GraphNodeSchema(BaseModel):
    labels: list[str]
    properties: dict[str, list[str]] = Field(default_factory=dict)


class GraphRelationSchema(BaseModel):
    type: str
    properties: dict[str, list[str]] = Field(default_factory=dict)
    start_labels: list[str] = Field(default_factory=list)
    end_labels: list[str] = Field(default_factory=list)


class GraphSchema(BaseModel):
    nodes: list[GraphNodeSchema] = Field(default_factory=list)
    relationships: list[GraphRelationSchema] = Field(default_factory=list)

    def to_prompt(self) -> str:
        return GRAPH_SCHEMA_PROMPT


def get_static_graph_schema() -> GraphSchema:
    """Constructs a static GraphSchema matching the fixed knowledge graph metamodel."""
    return GraphSchema(
        nodes=[
            GraphNodeSchema(
                labels=["Document"],
                properties={"filename": ["String"], "id": ["String"], "user_id": ["String"]},
            ),
            GraphNodeSchema(
                labels=["Entity"],
                properties={
                    "description": ["String"],
                    "name": ["String"],
                    "type": ["String"],
                    "user_id": ["String"],
                },
            ),
        ],
        relationships=[
            GraphRelationSchema(
                type="MENTIONS",
                start_labels=["Document"],
                end_labels=["Entity"],
            ),
            GraphRelationSchema(
                type="RELATED_TO",
                start_labels=["Entity"],
                end_labels=["Entity"],
                properties={"description": ["String"], "type": ["String"]},
            ),
        ],
    )
