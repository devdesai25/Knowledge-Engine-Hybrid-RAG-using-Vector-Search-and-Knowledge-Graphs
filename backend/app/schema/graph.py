from pydantic import BaseModel, Field

class Entity(BaseModel):
    name: str
    type: str
    description: str | None = None

class Relationship(BaseModel):
    source: str
    target: str
    type: str
    description: str | None = None

class GraphExtraction(BaseModel):
    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)