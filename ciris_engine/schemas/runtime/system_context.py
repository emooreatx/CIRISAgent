"""
System and runtime context schemas.

Provides type-safe contexts for system state and runtime operations.
"""
from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from pydantic import Field

class SystemSnapshot(BaseModel):
    """Complete system state snapshot for decision-making context."""
    
    # Core system state
    timestamp: datetime = Field(..., description="When snapshot was taken")
    runtime_phase: str = Field(..., description="Current runtime phase")
    active_services: Dict[str, bool] = Field(..., description="Service health status")
    
    # Resource tracking
    memory_usage_mb: float = Field(..., description="Current memory usage")
    cpu_usage_percent: float = Field(..., description="Current CPU usage")
    active_thoughts: int = Field(..., description="Number of active thoughts")
    active_tasks: int = Field(..., description="Number of active tasks")
    
    # Performance metrics
    avg_response_time_ms: float = Field(..., description="Average response time")
    error_rate: float = Field(..., description="Current error rate")
    queue_depth: int = Field(..., description="Message queue depth")
    
    # Audit trail
    last_audit_hash: Optional[str] = Field(None, description="Last audit chain hash")
    audit_entries_count: int = Field(0, description="Total audit entries")
    
    # Resource accounting
    current_round_resources: Optional['ResourceUsage'] = Field(None, description="Resources used this round")
    total_resources: Optional['ResourceUsage'] = Field(None, description="Total resources used")
    
    # Verification status
    last_audit_verification: Optional['AuditVerification'] = Field(None, description="Last audit verification")
    
    # Telemetry summary
    telemetry: Optional['TelemetrySummary'] = Field(None, description="Recent telemetry metrics")
    
    class Config:
        extra = "forbid"

class TaskContext(BaseModel):
    """Context for a specific task."""
    task_id: str = Field(..., description="Unique task identifier")
    channel_id: str = Field(..., description="Channel where task originated")
    created_at: datetime = Field(..., description="Task creation time")
    status: str = Field(..., description="Current task status")
    
    # Task metadata
    priority: int = Field(0, description="Task priority")
    retry_count: int = Field(0, description="Number of retries")
    parent_task_id: Optional[str] = Field(None, description="Parent task if nested")
    
    # Execution context
    assigned_agent: Optional[str] = Field(None, description="Agent handling the task")
    deadline: Optional[datetime] = Field(None, description="Task deadline")
    tags: List[str] = Field(default_factory=list, description="Task tags")
    
    # Results
    result: Optional[str] = Field(None, description="Task result")
    result_data: Optional[Dict[str, str]] = Field(None, description="Structured result data")
    error: Optional[str] = Field(None, description="Error if failed")
    
    class Config:
        extra = "forbid"

class ThoughtContext(BaseModel):
    """Context for a thought being processed."""
    thought_id: str = Field(..., description="Unique thought identifier")
    task_id: str = Field(..., description="Associated task ID")
    content: str = Field(..., description="Thought content")
    thought_type: str = Field(..., description="Type of thought")
    
    # Processing state
    created_at: datetime = Field(..., description="When thought was created")
    processing_depth: int = Field(0, description="How many times processed")
    is_pondering: bool = Field(False, description="Whether in ponder state")
    
    # Relationships
    parent_thought_id: Optional[str] = Field(None, description="Parent thought if nested")
    child_thought_ids: List[str] = Field(default_factory=list, description="Child thoughts")
    
    # DMA results (stored as JSON strings for flexibility)
    pdma_result: Optional[str] = Field(None, description="PDMA evaluation JSON")
    csdma_result: Optional[str] = Field(None, description="CSDMA evaluation JSON")
    dsdma_result: Optional[str] = Field(None, description="DSDMA evaluation JSON")
    
    # Decision
    selected_action: Optional[str] = Field(None, description="Action selected")
    decision_confidence: float = Field(0.0, description="Confidence in decision")
    
    class Config:
        extra = "forbid"

class UserProfile(BaseModel):
    """User profile information."""
    user_id: str = Field(..., description="Unique user identifier")
    display_name: str = Field(..., description="User display name")
    created_at: datetime = Field(..., description="Profile creation time")
    
    # Preferences
    preferred_language: str = Field("en", description="Preferred language code")
    timezone: str = Field("UTC", description="User timezone")
    communication_style: str = Field("formal", description="Preferred communication style")
    
    # Interaction history
    total_interactions: int = Field(0, description="Total interactions")
    last_interaction: Optional[datetime] = Field(None, description="Last interaction time")
    trust_level: float = Field(0.5, description="Trust level (0.0-1.0)")
    
    # Permissions
    is_wa: bool = Field(False, description="Whether user is Wise Authority")
    permissions: List[str] = Field(default_factory=list, description="Granted permissions")
    restrictions: List[str] = Field(default_factory=list, description="Applied restrictions")
    
    class Config:
        extra = "forbid"

class ChannelContext(BaseModel):
    """Context for a communication channel."""
    channel_id: str = Field(..., description="Unique channel identifier")
    channel_type: str = Field(..., description="Type of channel (discord, cli, api)")
    created_at: datetime = Field(..., description="Channel creation time")
    
    # Channel metadata
    channel_name: Optional[str] = Field(None, description="Human-readable channel name")
    is_private: bool = Field(False, description="Whether channel is private")
    participants: List[str] = Field(default_factory=list, description="Channel participants")
    
    # State
    is_active: bool = Field(True, description="Whether channel is active")
    last_activity: Optional[datetime] = Field(None, description="Last activity time")
    message_count: int = Field(0, description="Total messages in channel")
    
    # Configuration
    allowed_actions: List[str] = Field(default_factory=list, description="Allowed actions in channel")
    moderation_level: str = Field("standard", description="Moderation level")
    
    class Config:
        extra = "forbid"

class ResourceUsage(BaseModel):
    """Resource usage tracking."""
    tokens_used: int = Field(0, description="Tokens consumed")
    cost_cents: float = Field(0.0, description="Cost in cents")
    carbon_grams: float = Field(0.0, description="Carbon footprint in grams")
    compute_seconds: float = Field(0.0, description="Compute time in seconds")
    
    # Breakdown by service
    service_breakdown: Dict[str, Dict[str, float]] = Field(
        default_factory=dict,
        description="Resource usage per service"
    )
    
    class Config:
        extra = "forbid"

class AuditVerification(BaseModel):
    """Audit chain verification result."""
    verified_at: datetime = Field(..., description="When verification occurred")
    result: str = Field(..., description="Verification result: valid, invalid, partial")
    entries_verified: int = Field(..., description="Number of entries verified")
    hash_chain_valid: bool = Field(..., description="Whether hash chain is intact")
    signatures_valid: bool = Field(..., description="Whether signatures are valid")
    
    # Issues found
    issues: List[str] = Field(default_factory=list, description="Issues found during verification")
    missing_entries: List[str] = Field(default_factory=list, description="Missing entry IDs")
    
    class Config:
        extra = "forbid"

class ConscienceResult(BaseModel):
    """Result from conscience evaluation."""
    passed: bool = Field(..., description="Whether consciences passed")
    conscience_name: str = Field(..., description="Name of conscience")
    reason: Optional[str] = Field(None, description="Reason for pass/fail")
    severity: str = Field("info", description="Severity: info, warning, error, critical")
    
    # Override capability
    can_override: bool = Field(False, description="Whether can be overridden")
    override_reason: Optional[str] = Field(None, description="Reason for override")
    overridden: bool = Field(False, description="Whether was overridden")
    overridden_by: Optional[str] = Field(None, description="Who overrode")
    
    class Config:
        extra = "forbid"

class TaskSummary(BaseModel):
    """Summary of a task for context."""
    task_id: str = Field(..., description="Task ID")
    description: Optional[str] = Field(None, description="Task description")
    priority: Optional[int] = Field(None, description="Task priority")
    status: Optional[str] = Field(None, description="Task status")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    
    class Config:
        extra = "allow"

class ThoughtSummary(BaseModel):
    """Summary of a thought for context."""
    thought_id: str = Field(..., description="Thought ID")
    content: Optional[str] = Field(None, description="Thought content")
    status: Optional[str] = Field(None, description="Thought status")
    source_task_id: Optional[str] = Field(None, description="Source task ID")
    thought_type: Optional[str] = Field(None, description="Type of thought")
    thought_depth: Optional[int] = Field(None, description="Processing depth")
    
    class Config:
        extra = "allow"

class TelemetrySummary(BaseModel):
    """Summary of recent telemetry metrics for system context."""
    
    # Time window
    window_start: datetime = Field(..., description="Start of telemetry window")
    window_end: datetime = Field(..., description="End of telemetry window")
    uptime_seconds: float = Field(..., description="System uptime in seconds")
    
    # Activity metrics (last 24h)
    messages_processed_24h: int = Field(0, description="Messages processed in last 24h")
    thoughts_processed_24h: int = Field(0, description="Thoughts processed in last 24h")
    tasks_completed_24h: int = Field(0, description="Tasks completed in last 24h")
    errors_24h: int = Field(0, description="Errors in last 24h")
    
    # Current hour metrics
    messages_current_hour: int = Field(0, description="Messages this hour")
    thoughts_current_hour: int = Field(0, description="Thoughts this hour")
    errors_current_hour: int = Field(0, description="Errors this hour")
    
    # Service breakdowns
    service_calls: Dict[str, int] = Field(default_factory=dict, description="Calls per service type")
    service_errors: Dict[str, int] = Field(default_factory=dict, description="Errors per service type")
    service_latency_ms: Dict[str, float] = Field(default_factory=dict, description="Avg latency per service")
    
    # Resource consumption rates
    tokens_per_hour: float = Field(0.0, description="Average tokens per hour")
    cost_per_hour_cents: float = Field(0.0, description="Average cost per hour in cents")
    carbon_per_hour_grams: float = Field(0.0, description="Average carbon per hour in grams")
    
    # Health indicators
    error_rate_percent: float = Field(0.0, description="Error rate as percentage")
    avg_thought_depth: float = Field(0.0, description="Average thought processing depth")
    queue_saturation: float = Field(0.0, description="Queue saturation 0-1")
    
    class Config:
        extra = "forbid"

__all__ = [
    "SystemSnapshot",
    "TaskContext", 
    "ThoughtContext",
    "UserProfile",
    "ChannelContext",
    "ResourceUsage",
    "AuditVerification",
    "TelemetrySummary",
    "ConscienceResult",
    "TaskSummary",
    "ThoughtSummary"
]