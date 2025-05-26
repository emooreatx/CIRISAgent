from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

# Import enums from foundational_schemas_v1
from .foundational_schemas_v1 import TaskStatus, ThoughtStatus

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
    round_number: int = 0  # Simplified from round_created/round_processed
    content: str
    context: Dict[str, Any] = Field(default_factory=dict)  # Renamed from processing_context
    ponder_count: int = 0
    ponder_notes: Optional[List[str]] = None
    parent_thought_id: Optional[str] = None  # Renamed from related_thought_id
    final_action: Dict[str, Any] = Field(default_factory=dict)  # Simplified from final_action_result
