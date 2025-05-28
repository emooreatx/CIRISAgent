from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict

class SystemSnapshot(BaseModel):
    current_task_details: Optional[Dict[str, Any]] = None
    current_thought_summary: Optional[Dict[str, Any]] = None
    system_counts: Dict[str, int] = Field(default_factory=dict)
    top_pending_tasks_summary: List[Dict[str, Any]] = Field(default_factory=list)
    recently_completed_tasks_summary: List[Dict[str, Any]] = Field(default_factory=list)
    user_profiles: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(extra="allow")

class ThoughtContext(BaseModel):
    system_snapshot: SystemSnapshot
    user_profiles: Dict[str, Any] = Field(default_factory=dict)
    task_history: List[Dict[str, Any]] = Field(default_factory=list)
    identity_context: Optional[str] = None
