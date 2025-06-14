"""
Runtime Control Schemas v1

Pydantic schemas for runtime control operations, adapter management,
and system state tracking.
"""

from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field

from .versioning import SchemaVersion


class AdapterConfigSchema(BaseModel):
    """Schema for adapter configuration"""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    
    adapter_type: str  # 'discord', 'cli', 'api', etc.
    instance_id: Optional[str] = None  # Unique identifier for this adapter instance
    
    # Common configuration fields
    enabled: bool = True
    auto_start: bool = True
    priority: str = "normal"  # 'low', 'normal', 'high'
    
    # Adapter-specific configuration
    config: Dict[str, Any] = Field(default_factory=dict)
    
    # Profile association
    profile_name: Optional[str] = None
    
    # Service configuration
    service_overrides: Dict[str, Any] = Field(default_factory=dict)


class ProcessorMetrics(BaseModel):
    """Detailed processor performance metrics"""
    total_rounds: int = 0
    successful_rounds: int = 0
    failed_rounds: int = 0
    avg_round_time_ms: float = 0.0
    
    thoughts_processed: int = 0
    thoughts_failed: int = 0
    thoughts_deferred: int = 0
    
    last_round_time: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count_24h: int = 0


class AdapterMetrics(BaseModel):
    """Adapter performance and activity metrics"""
    messages_received: int = 0
    messages_sent: int = 0
    actions_executed: int = 0
    errors_count: int = 0
    
    uptime_seconds: float = 0.0
    last_activity: Optional[datetime] = None
    connection_status: str = "unknown"  # 'connected', 'disconnected', 'error'
    
    # Channel/platform specific metrics
    channels_active: int = 0
    platform_specific: Dict[str, Any] = Field(default_factory=dict)


class ServiceMetrics(BaseModel):
    """Service performance metrics"""
    requests_handled: int = 0
    requests_failed: int = 0
    avg_response_time_ms: float = 0.0
    
    circuit_breaker_trips: int = 0
    last_health_check: Optional[datetime] = None
    health_status: str = "unknown"


class RuntimeControlEvent(BaseModel):
    """Event record for runtime control operations"""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    
    event_id: str
    event_type: str  # 'processor_start', 'adapter_load', 'config_reload', etc.
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Operation details
    operation: str
    target: Optional[str] = None  # adapter_id, processor, etc.
    
    # Results
    success: bool
    details: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    
    # Context
    user_agent: Optional[str] = None
    source_ip: Optional[str] = None
    correlation_id: Optional[str] = None


class RuntimeSnapshot(BaseModel):
    """Comprehensive runtime state snapshot"""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    runtime_version: str = "1.0.0"
    uptime_seconds: float = 0.0
    
    processor_running: bool = False
    processor_metrics: ProcessorMetrics = Field(default_factory=ProcessorMetrics)
    
    adapters_loaded: int = 0
    adapters_active: int = 0
    adapter_details: List[Dict[str, Any]] = Field(default_factory=list)
    
    services_registered: int = 0
    service_health: Dict[str, str] = Field(default_factory=dict)
    
    active_profile: Optional[str] = None
    config_version: Optional[str] = None
    
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    
    overall_health: str = "unknown"  # 'healthy', 'degraded', 'critical', 'error'
    health_details: Dict[str, Any] = Field(default_factory=dict)


class AdapterOperation(BaseModel):
    """Schema for adapter operations (load/unload/start/stop)"""
    operation_type: str  # 'load', 'unload', 'start', 'stop'
    adapter_id: str
    adapter_type: str
    config: Optional[AdapterConfigSchema] = None
    
    # Load-specific options
    auto_start: bool = True
    profile_name: Optional[str] = None
    
    # Operational flags
    force: bool = False  # Force operation even if adapter is in use
    graceful_timeout_seconds: int = 30


class ProcessorOperation(BaseModel):
    """Schema for processor operations"""
    operation_type: str  # 'start', 'stop', 'pause', 'resume', 'single_step'
    
    num_rounds: Optional[int] = None
    
    graceful_timeout_seconds: int = 30
    force: bool = False
    
    step_timeout_seconds: int = 60
    
    requested_by: Optional[str] = None
    reason: Optional[str] = None


class ConfigurationUpdate(BaseModel):
    """Schema for configuration updates"""
    update_type: str  # 'reload', 'profile_update', 'profile_switch'
    
    # Reload options
    config_path: Optional[str] = None
    
    # Profile operations
    profile_name: Optional[str] = None
    profile_data: Optional[Dict[str, Any]] = None
    
    # Update options
    validate_only: bool = False
    backup_current: bool = True
    apply_immediately: bool = True


class RuntimeControlCommand(BaseModel):
    """Unified command schema for runtime control operations"""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    
    command_id: str
    command_type: str  # 'processor', 'adapter', 'config', 'system'
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    processor_operation: Optional[ProcessorOperation] = None
    adapter_operation: Optional[AdapterOperation] = None
    config_operation: Optional[ConfigurationUpdate] = None
    
    requested_by: Optional[str] = None
    correlation_id: Optional[str] = None
    timeout_seconds: int = 300


class RuntimeControlResponse(BaseModel):
    """Unified response schema for runtime control operations"""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    
    command_id: str
    success: bool
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Operation results
    operation_type: str
    status: str
    message: Optional[str] = None
    
    # Detailed results
    data: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    
    # Timing
    execution_time_ms: int = 0
    
    # State changes
    state_before: Optional[Dict[str, Any]] = None
    state_after: Optional[Dict[str, Any]] = None
