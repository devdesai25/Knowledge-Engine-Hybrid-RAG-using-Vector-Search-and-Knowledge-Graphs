from pydantic import BaseModel, Field
from typing import Any

class metadata(BaseModel):
    name: str
    value: str

class RetreivalResult(BaseModel):
    content: str
    score: float
    metadata: list[metadata]

class GraphParameter(BaseModel):
    name: str
    value: Any = ""

class GraphQuery(BaseModel):
    query: str
    explanation: str
    parameters: list[GraphParameter]
