from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

# Import enums from foundational_schemas_v1
from .foundational_schemas_v1 import TaskStatus, ThoughtStatus
from .action_params_v1 import (
    ObserveParams,
    SpeakParams,
    ToolParams,
    PonderParams,
    RejectParams,
    DeferParams,
    MemorizeParams,
    RememberParams,
    ForgetParams,
)
from .dma_results_v1 import ActionSelectionResult

class Task(BaseModel):
    """Core task object - minimal v1"""
    schema_version: str = "1.0"
    task_id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    created_at: str  # ISO8601
    updated_at: str  # ISO8601
    parent_task_id: Optional[str] = None  # Simplified from parent_goal_id
    context: Dict[str, Any] = Field(default_factory=dict)
    outcome: Dict[str, Any] = Field(default_factory=dict)

class Thought(BaseModel):
    """Core thought object - minimal v1"""
    schema_version: str = "1.0"
    thought_id: str
    source_task_id: str
    thought_type: str = "standard"  # simplified
    status: ThoughtStatus = ThoughtStatus.PENDING
    created_at: str
    updated_at: str
    round_number: int = Field(default=0, alias="round_created")
    content: str
    context: Dict[str, Any] = Field(default_factory=dict)  # Renamed from processing_context
    ponder_count: int = 0
    ponder_notes: Optional[List[str]] = None
    parent_thought_id: Optional[str] = None  # Renamed from related_thought_id
    final_action: Dict[str, Any] = Field(default_factory=dict)  # Simplified from final_action_result


class ActionSelectionPDMAResult(BaseModel):
    """Compatibility result model expected by legacy tests."""

    context_summary_for_action_selection: str
    action_alignment_check: Dict[str, Any]
    selected_handler_action: Any
    action_parameters: Any
    action_selection_rationale: str
    monitoring_for_selected_action: Any
    confidence_score: Optional[float] = None
    action_conflicts: Optional[Any] = None
    action_resolution: Optional[Any] = None
    raw_llm_response: Optional[str] = None
    ethical_assessment_summary: Optional[Dict[str, Any]] = None
    csdma_assessment_summary: Optional[Dict[str, Any]] = None
    dsdma_assessment_summary: Optional[Dict[str, Any]] = None


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
    "RememberParams",
    "ForgetParams",
    "ActionSelectionResult",
    "ActionSelectionPDMAResult",
]

