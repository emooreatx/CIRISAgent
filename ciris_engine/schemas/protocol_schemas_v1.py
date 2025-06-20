"""
Schemas for service protocol interfaces to replace Dict[str, Any] usage.

These schemas provide type safety for all protocol method parameters and returns.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from enum import Enum

from .foundational_schemas_v1 import HandlerActionType


# Memory Service Schemas

class MemorySearchResult(BaseModel):
    """Result from memory search operation."""
    node_id: str = Field(..., description="Unique identifier of the memory node")
    content: str = Field(..., description="Memory content")
    node_type: str = Field(..., description="Type of memory node")
    relevance_score: float = Field(..., description="Relevance score (0.0-1.0)")
    created_at: datetime = Field(..., description="When the memory was created")
    metadata: Optional[Dict[str, str]] = Field(default=None, description="Additional metadata")


class TimeSeriesDataPoint(BaseModel):
    """A time-series data point from memory correlations."""
    timestamp: datetime = Field(..., description="Time of the data point")
    metric_name: str = Field(..., description="Name of the metric")
    value: float = Field(..., description="Metric value")
    correlation_type: str = Field(..., description="Type of correlation (e.g., METRIC_DATAPOINT)")
    tags: Optional[Dict[str, str]] = Field(default=None, description="Optional tags")
    source: Optional[str] = Field(default=None, description="Source of the data")


class IdentityUpdateRequest(BaseModel):
    """Request to update identity graph."""
    node_id: Optional[str] = Field(None, description="Specific node to update")
    updates: Dict[str, Union[str, int, float, bool]] = Field(..., description="Fields to update")
    source: str = Field(..., description="Source of the update (e.g., 'wa_feedback')")
    reason: Optional[str] = Field(None, description="Reason for the update")


class EnvironmentUpdateRequest(BaseModel):
    """Request to update environment graph."""
    adapter_type: str = Field(..., description="Type of adapter providing update")
    environment_data: Dict[str, Any] = Field(..., description="Environment data to merge")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When update occurred")


# Tool Service Schemas

class ToolParameterSchema(BaseModel):
    """Schema for a tool parameter."""
    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type (string, integer, etc.)")
    description: str = Field(..., description="Human-readable description")
    required: bool = Field(True, description="Whether parameter is required")
    default: Optional[Any] = Field(None, description="Default value if not provided")
    enum: Optional[List[Any]] = Field(None, description="Valid values for enum parameters")
    pattern: Optional[str] = Field(None, description="Regex pattern for validation")


class ToolInfo(BaseModel):
    """Complete information about a tool including its source."""
    tool_name: str = Field(..., description="Name of the tool")
    display_name: str = Field(..., description="Human-friendly display name")
    description: str = Field(..., description="What the tool does")
    category: str = Field(..., description="Tool category")
    
    # Adapter identification
    adapter_id: str = Field(..., description="ID of the adapter providing this tool")
    adapter_type: str = Field(..., description="Type of adapter (discord, cli, etc.)")
    adapter_instance_name: Optional[str] = Field(None, description="Human-friendly adapter instance name")
    
    # Schema information
    parameters: List[ToolParameterSchema] = Field(default_factory=list, description="Tool parameters")
    returns_schema: Optional[Dict[str, Any]] = Field(None, description="Schema of return value")
    
    # Usage information
    examples: Optional[List[Dict[str, Any]]] = Field(None, description="Example invocations")
    requires_auth: bool = Field(False, description="Whether tool requires authentication")
    rate_limit: Optional[int] = Field(None, description="Rate limit per minute")
    timeout_seconds: float = Field(30.0, description="Default timeout")
    
    # Availability
    enabled: bool = Field(True, description="Whether tool is currently enabled")
    health_status: Optional[str] = Field(None, description="Current health status")


class ToolExecutionRequest(BaseModel):
    """Request to execute a tool."""
    tool_name: str = Field(..., description="Name of the tool to execute")
    adapter_id: Optional[str] = Field(None, description="Specific adapter to use (for disambiguation)")
    parameters: Dict[str, Union[str, int, float, bool, List, Dict]] = Field(
        default_factory=dict, 
        description="Tool parameters with typed values"
    )
    timeout: Optional[float] = Field(None, description="Execution timeout in seconds")
    correlation_id: Optional[str] = Field(None, description="For tracking async execution")


class ToolExecutionResult(BaseModel):
    """Result from tool execution."""
    success: bool = Field(..., description="Whether execution succeeded")
    result: Optional[Any] = Field(None, description="Tool execution result")
    error: Optional[str] = Field(None, description="Error message if failed")
    execution_time: float = Field(..., description="Execution time in seconds")
    output: Optional[str] = Field(None, description="Tool output/logs")
    adapter_id: str = Field(..., description="ID of adapter that executed the tool")
    metadata: Optional[Dict[str, str]] = Field(None, description="Additional metadata")


# Audit Service Schemas

class ActionContext(BaseModel):
    """Context for an audited action."""
    thought_id: str = Field(..., description="ID of the thought initiating action")
    task_id: str = Field(..., description="ID of the associated task")
    handler_name: str = Field(..., description="Name of the action handler")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Action parameters")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class GuardrailCheckResult(BaseModel):
    """Result from a guardrail check."""
    allowed: bool = Field(..., description="Whether action is allowed")
    reason: Optional[str] = Field(None, description="Reason for allow/deny")
    modifications: Optional[Dict[str, Any]] = Field(None, description="Suggested modifications")
    risk_level: Optional[str] = Field(None, description="Assessed risk level")


class AuditEntry(BaseModel):
    """An entry in the audit trail."""
    entry_id: str = Field(..., description="Unique audit entry ID")
    timestamp: datetime = Field(..., description="When the event occurred")
    entity_id: str = Field(..., description="ID of entity being audited")
    event_type: str = Field(..., description="Type of event")
    actor: str = Field(..., description="Who/what performed the action")
    details: Dict[str, Any] = Field(..., description="Event details")
    outcome: Optional[str] = Field(None, description="Event outcome")


# LLM Service Schemas

class LLMStatus(BaseModel):
    """Status information from LLM service."""
    available: bool = Field(..., description="Whether service is available")
    model: str = Field(..., description="Current model name")
    usage: Dict[str, int] = Field(
        default_factory=dict,
        description="Token usage statistics"
    )
    rate_limit_remaining: Optional[int] = Field(None, description="Remaining API calls")
    response_time_avg: Optional[float] = Field(None, description="Average response time")


# Network Service Schemas

class NetworkQueryRequest(BaseModel):
    """Request for network query."""
    query_type: str = Field(..., description="Type of query (e.g., 'peer_discovery')")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Query parameters")
    timeout: Optional[float] = Field(30.0, description="Query timeout")


# Telemetry Service Schemas

class MetricDataPoint(BaseModel):
    """A single metric data point."""
    metric_name: str = Field(..., description="Name of the metric")
    value: float = Field(..., description="Metric value")
    timestamp: datetime = Field(..., description="When metric was recorded")
    tags: Optional[Dict[str, str]] = Field(None, description="Metric tags")
    service_name: Optional[str] = Field(None, description="Service that recorded metric")


class ServiceStatus(BaseModel):
    """Status of a service."""
    service_name: str = Field(..., description="Name of the service")
    status: str = Field(..., description="Service status (healthy/unhealthy/degraded)")
    uptime_seconds: Optional[float] = Field(None, description="Service uptime")
    last_heartbeat: Optional[datetime] = Field(None, description="Last heartbeat time")
    metrics: Optional[Dict[str, float]] = Field(None, description="Recent metrics")


class ResourceLimits(BaseModel):
    """Resource limits and quotas."""
    max_memory_mb: Optional[int] = Field(None, description="Maximum memory in MB")
    max_cpu_percent: Optional[float] = Field(None, description="Maximum CPU percentage")
    max_disk_gb: Optional[float] = Field(None, description="Maximum disk usage in GB")
    max_api_calls_per_minute: Optional[int] = Field(None, description="API rate limit")
    max_concurrent_operations: Optional[int] = Field(None, description="Max concurrent ops")


# Runtime Control Schemas

class ProcessorQueueStatus(BaseModel):
    """Status of the processor queue."""
    queue_size: int = Field(..., description="Number of items in queue")
    processing: bool = Field(..., description="Whether actively processing")
    current_item: Optional[str] = Field(None, description="Currently processing item")
    items_processed: int = Field(..., description="Total items processed")
    average_processing_time: Optional[float] = Field(None, description="Avg processing time")


class AdapterConfig(BaseModel):
    """Configuration for loading an adapter."""
    adapter_class: str = Field(..., description="Fully qualified adapter class name")
    initialization_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for adapter initialization"
    )
    auto_start: bool = Field(True, description="Whether to start adapter immediately")


class AdapterInfo(BaseModel):
    """Information about a loaded adapter."""
    adapter_id: str = Field(..., description="Unique adapter ID")
    adapter_type: str = Field(..., description="Type of adapter")
    status: str = Field(..., description="Adapter status (active/inactive/error)")
    loaded_at: datetime = Field(..., description="When adapter was loaded")
    configuration: Dict[str, Any] = Field(..., description="Adapter configuration")
    metrics: Optional[Dict[str, float]] = Field(None, description="Adapter metrics")


class ConfigValue(BaseModel):
    """A configuration value with metadata."""
    path: str = Field(..., description="Configuration path")
    value: Any = Field(..., description="Configuration value")
    type: str = Field(..., description="Value type")
    sensitive: bool = Field(False, description="Whether value is sensitive")
    source: Optional[str] = Field(None, description="Configuration source")
    last_modified: Optional[datetime] = Field(None, description="Last modification time")


# Secrets Service Schemas

class SecretInfo(BaseModel):
    """Information about a stored secret."""
    uuid: str = Field(..., description="Secret UUID")
    description: str = Field(..., description="Secret description")
    secret_type: str = Field(..., description="Type of secret")
    sensitivity: str = Field(..., description="Sensitivity level")
    created_at: datetime = Field(..., description="When secret was stored")
    last_accessed: Optional[datetime] = Field(None, description="Last access time")
    access_count: int = Field(0, description="Number of times accessed")
    decrypted_value: Optional[str] = Field(None, description="Decrypted value if requested")


class SecretsServiceStats(BaseModel):
    """Statistics from secrets service."""
    secrets_stored: int = Field(..., description="Total secrets in storage")
    filter_active: bool = Field(..., description="Whether filter is active")
    patterns_enabled: List[str] = Field(..., description="Enabled detection patterns")
    recent_detections: int = Field(0, description="Detections in last hour")
    storage_size_bytes: Optional[int] = Field(None, description="Storage size used")