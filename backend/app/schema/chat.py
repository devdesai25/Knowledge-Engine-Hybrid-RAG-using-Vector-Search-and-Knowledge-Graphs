from typing import Any
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    query: str

class MultiHopDecision(BaseModel):
    is_complete: bool = Field(
        ...,
        description="True if the current accumulated graph evidence is sufficient to answer the question, False if another hop is needed."
    )
    reasoning: str = Field(
        ...,
        description="Detailed explanation of what facts were verified and what missing connection or bridge entity should be explored next."
    )
    next_cypher_query: str | None = Field(
        default=None,
        description="A valid read-only Cypher query for the next hop. Must filter by $user_id and end with LIMIT 20. Null if is_complete is True."
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Query parameters for next_cypher_query."
    )
