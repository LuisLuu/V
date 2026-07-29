from pydantic import BaseModel, Field, ValidationError
from typing import List, Dict, Any

class ToolCall(BaseModel):
    name: str
    args: Dict[str, Any] = Field(default_factory=dict)

class CognitivePlan(BaseModel):
    tool_calls: List[ToolCall] = Field(default_factory=list)

class TagResult(BaseModel):
    row_id: int
    tags: List[str]

class BatchTagResponse(BaseModel):
    results: List[TagResult] = Field(default_factory=list)