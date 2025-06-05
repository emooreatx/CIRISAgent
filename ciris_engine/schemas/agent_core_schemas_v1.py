from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from .foundational_schemas_v1 import TaskStatus, ThoughtStatus
from .action_params_v1 import (
    ObserveParams,
    SpeakParams,
    ToolParams,
    PonderParams,
    RejectParams,
    DeferParams,
    MemorizeParams,
    RecallParams,
    ForgetParams,
)
from .dma_results_v1 import ActionSelectionResult
from .context_schemas_v1 import ThoughtContext

class Task(BaseModel):
    """Core task object - minimal v1"""
    task_id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    created_at: str  # ISO8601
    updated_at: str  # ISO8601
    parent_task_id: Optional[str] = None
    context: Optional[ThoughtContext] = Field(default=None, description="Context object")
    outcome: Dict[str, Any] = Field(default_factory=dict)

class Thought(BaseModel):
    """Core thought object - minimal v1"""
    thought_id: str
    source_task_id: str
    thought_type: str = "standard"
    status: ThoughtStatus = ThoughtStatus.PENDING
    created_at: str
    updated_at: str
    round_number: int = 0
    content: str
    context: Optional[ThoughtContext] = Field(default=None, description="Context object")
    ponder_count: int = 0
    ponder_notes: Optional[List[str]] = None
    parent_thought_id: Optional[str] = None
    final_action: Dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "Task",
    "Thought",
    "ObserveParams",
    "SpeakParams",
    "ToolParams",
    "PonderParams",
    "RejectParams",
    "DeferParams",
    "MemorizeParams",
    "RecallParams",
    "ForgetParams",
    "ActionSelectionResult",
]

