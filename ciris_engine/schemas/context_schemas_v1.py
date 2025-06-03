from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, ConfigDict

class TaskSummary(BaseModel):
    """Summary of a task for context."""
    task_id: str
    description: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    created_at: Optional[str] = None
    model_config = ConfigDict(extra="allow")

class ThoughtSummary(BaseModel):
    """Summary of a thought for context."""
    thought_id: str
    content: Optional[str] = None
    status: Optional[str] = None
    source_task_id: Optional[str] = None
    thought_type: Optional[str] = None
    ponder_count: Optional[int] = None
    model_config = ConfigDict(extra="allow")

class UserProfile(BaseModel):
    """User profile information."""
    name: Optional[str] = None
    id: Optional[str] = None
    display_name: Optional[str] = None
    model_config = ConfigDict(extra="allow")

class SystemSnapshot(BaseModel):
    current_task_details: Optional[TaskSummary] = None
    current_thought_summary: Optional[ThoughtSummary] = None
    system_counts: Dict[str, int] = Field(default_factory=dict)
    top_pending_tasks_summary: List[TaskSummary] = Field(default_factory=list)
    recently_completed_tasks_summary: List[TaskSummary] = Field(default_factory=list)
    user_profiles: Optional[Dict[str, UserProfile]] = None
    channel_id: Optional[str] = None
    model_config = ConfigDict(extra="allow")

class TaskContext(BaseModel):
    """Context information from the original task."""
    author_name: Optional[str] = None
    author_id: Optional[str] = None
    channel_id: Optional[str] = None
    origin_service: Optional[str] = None
    model_config = ConfigDict(extra="allow")

class ThoughtContext(BaseModel):
    system_snapshot: SystemSnapshot
    user_profiles: Dict[str, UserProfile] = Field(default_factory=dict)
    task_history: List[TaskSummary] = Field(default_factory=list)
    identity_context: Optional[str] = None
    initial_task_context: Optional[TaskContext] = None
