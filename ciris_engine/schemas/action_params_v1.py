# --- v1 Action Params Schemas ---
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from .graph_schemas_v1 import GraphScope

class ObserveParams(BaseModel):
    channel_id: Optional[str] = None
    active: bool = False
    context: dict = Field(default_factory=dict)

    def __init__(self, **data):
        if 'context' not in data or data['context'] is None:
            data['context'] = {}
        super().__init__(**data)

class SpeakParams(BaseModel):
    channel_id: Optional[str] = None
    content: str

class ToolParams(BaseModel):  # Renamed from ActParams
    name: str
    args: Dict[str, Any] = Field(default_factory=dict)

class PonderParams(BaseModel):
    questions: List[str]

class RejectParams(BaseModel):
    reason: str

class DeferParams(BaseModel):
    reason: str
    context: Dict[str, Any] = Field(default_factory=dict)

class MemorizeParams(BaseModel):
    key: str  # What to remember
    value: Any  # The memory content
    scope: GraphScope = GraphScope.LOCAL

class RememberParams(BaseModel):
    query: str
    scope: GraphScope = GraphScope.LOCAL

class ForgetParams(BaseModel):
    key: str
    scope: GraphScope = GraphScope.LOCAL
    reason: str