# --- v1 Action Params Schemas ---
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class ObserveParams(BaseModel):
    channel_id: Optional[str] = None
    active: bool = False
    context: Dict[str, Any] = Field(default_factory=dict)

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
    scope: str = "local"  # local/identity/environment

class RememberParams(BaseModel):
    query: str
    scope: str = "local"

class ForgetParams(BaseModel):
    key: str
    scope: str = "local"
    reason: str