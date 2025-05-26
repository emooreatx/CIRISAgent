# --- v1 Action Params Schemas ---
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class ObserveParams(BaseModel):
    sources: List[str]
    active: bool = False  # Renamed from perform_active_look

class SpeakParams(BaseModel):
    content: str
    channel_id: Optional[str] = None

class ToolParams(BaseModel):  # Renamed from ActParams
    name: str
    args: Dict[str, Any] = {}

class PonderParams(BaseModel):
    questions: List[str]  # Renamed from key_questions

class RejectParams(BaseModel):
    reason: str

class DeferParams(BaseModel):
    reason: str
    context: Dict[str, Any] = Field(default_factory=dict)  # Simplified from deferral_package_content

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