from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from .wisdom_schemas_v1 import WisdomRequest
from .community_schemas_v1 import CommunityHealth
from .telemetry_schemas_v1 import CompactTelemetry
from .resource_schemas_v1 import ResourceSnapshot
from .secrets_schemas_v1 import SecretReference

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
    
    detected_secrets: List[SecretReference] = Field(default_factory=list)
    secrets_filter_version: int = 0
    total_secrets_stored: int = 0
    
    agent_name: Optional[str] = None
    network_status: Optional[str] = None
    isolation_hours: int = 0
    
    community_health: Optional[int] = None

    memory_available_mb: Optional[int] = None
    cpu_available: Optional[int] = None
    
    wisdom_source_available: Optional[str] = None
    wisdom_request: Optional[WisdomRequest] = None

    telemetry: Optional[CompactTelemetry] = None

    resources: Optional[ResourceSnapshot] = None
    resource_actions_taken: Dict[str, int] = Field(default_factory=dict)
    
    model_config = ConfigDict(extra="allow")

class TaskContext(BaseModel):
    """Context information from the original task."""
    author_name: Optional[str] = None
    author_id: Optional[str] = None
    channel_id: Optional[str] = None
    origin_service: Optional[str] = None
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

class ThoughtContext(BaseModel):
    system_snapshot: SystemSnapshot = Field(default_factory=SystemSnapshot)
    user_profiles: Dict[str, UserProfile] = Field(default_factory=dict)
    task_history: List[TaskSummary] = Field(default_factory=list)
    identity_context: Optional[str] = None
    initial_task_context: Optional[TaskContext] = None
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Dictionary-style access for backward compatibility."""
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)
