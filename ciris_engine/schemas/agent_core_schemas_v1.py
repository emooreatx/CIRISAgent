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
    task_id: ThoughtStatus
    description: ThoughtStatus
    status: TaskStatus = TaskStatus.PENDING
    priority: ThoughtStatus = 0
    created_at: ThoughtStatus  # ISO8601
    updated_at: ThoughtStatus  # ISO8601
    parent_task_id: Optional[str] = None
    context: Optional[ThoughtContext] = Field(default=None, description="Context object")
    outcome: Dict[str, Any] = Field(default_factory=dict)

class Thought(BaseModel):
    """Core thought object - minimal v1"""
    thought_id: ThoughtStatus
    source_task_id: ThoughtStatus
    thought_type: ThoughtStatus = "standard"
    status: ThoughtStatus = ThoughtStatus.PENDING
    created_at: ThoughtStatus
    updated_at: ThoughtStatus
    round_number: ThoughtStatus = 0
    content: ThoughtStatus
    context: Optional[ThoughtContext] = Field(default=None, description="Context object")
    ponder_count: ThoughtStatus = 0
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

