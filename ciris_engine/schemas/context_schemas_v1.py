from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from .wisdom_schemas_v1 import WisdomRequest
from .telemetry_schemas_v1 import CompactTelemetry
from .resource_schemas_v1 import ResourceSnapshot, ResourceUsageMetrics
from .secrets_schemas_v1 import SecretReference
from .audit_verification_schemas_v1 import AuditVerificationReport, ContinuousVerificationStatus
from .foundational_schemas_v1 import ResourceUsage
from .identity_schemas_v1 import ShutdownContext

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
    thought_depth: Optional[int] = None
    model_config = ConfigDict(extra="allow")

class UserProfile(BaseModel):
    """User profile information."""
    name: Optional[str] = None
    id: Optional[str] = None
    display_name: Optional[str] = None
    model_config = ConfigDict(extra="allow")


class ChannelContext(BaseModel):
    """Channel context information for consistent channel handling."""
    channel_id: str = Field(description="The unique identifier for the channel")
    channel_name: Optional[str] = Field(default=None, description="Human-readable channel name")
    channel_type: Optional[str] = Field(default=None, description="Type of channel (discord, cli, api, etc.)")
    is_monitored: bool = Field(default=True, description="Whether this channel is actively monitored")
    is_deferral: bool = Field(default=False, description="Whether this is a WA deferral channel")
    is_home: bool = Field(default=False, description="Whether this is the agent's home channel")
    permissions: List[str] = Field(default_factory=list, description="Channel-specific permissions")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional channel-specific data")
    
    # Channel preferences
    response_format: Optional[str] = Field(default=None, description="Preferred response format for this channel")
    max_message_length: Optional[int] = Field(default=None, description="Maximum message length for this channel")
    
    model_config = ConfigDict(extra="allow")


class SystemSnapshot(BaseModel):
    current_task_details: Optional[TaskSummary] = None
    current_thought_summary: Optional[ThoughtSummary] = None
    system_counts: Dict[str, int] = Field(default_factory=dict)
    top_pending_tasks_summary: List[TaskSummary] = Field(default_factory=list)
    recently_completed_tasks_summary: List[TaskSummary] = Field(default_factory=list)
    user_profiles: Optional[Dict[str, UserProfile]] = None
    channel_context: Optional[ChannelContext] = None
    
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
    
    # Resource transparency - AI can see its exact costs
    current_round_resources: Optional[ResourceUsage] = Field(
        default=None,
        description="Resource usage for current processing round"
    )
    session_total_resources: Optional[ResourceUsageMetrics] = Field(
        default=None, 
        description="Total resource usage for this session"
    )
    
    # Audit verification visibility - AI knows when its logs were verified
    last_audit_verification: Optional[AuditVerificationReport] = Field(
        default=None,
        description="Most recent audit trail verification report"
    )
    continuous_audit_status: Optional[ContinuousVerificationStatus] = Field(
        default=None,
        description="Status of continuous audit verification"
    )
    
    # Identity graph state - loaded once at snapshot generation
    agent_identity: Optional[Dict[str, Any]] = None
    identity_purpose: Optional[str] = None
    identity_capabilities: List[str] = Field(default_factory=list)
    identity_restrictions: List[str] = Field(default_factory=list)
    
    # Shutdown context - populated during graceful shutdown
    shutdown_context: Optional[ShutdownContext] = Field(
        default=None,
        description="Context for graceful shutdown negotiation"
    )
    
    # Service health and status
    service_health: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Health status of all registered services"
    )
    circuit_breaker_status: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Circuit breaker status for protected services"
    )
    
    model_config = ConfigDict(extra="allow")

class TaskContext(BaseModel):
    """Context information from the original task."""
    author_name: Optional[str] = None
    author_id: Optional[str] = None
    channel_context: Optional[ChannelContext] = None
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
