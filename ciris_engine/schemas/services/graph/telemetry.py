"""
Telemetry operations schemas for graph telemetry service.

Replaces Dict[str, Any] in telemetry service operations.
"""
from typing import Dict, List, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field


class TelemetrySnapshotResult(BaseModel):
    """Result of processing a system snapshot for telemetry."""
    memories_created: int = Field(0, description="Number of memory nodes created")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")
    consolidation_triggered: bool = Field(False, description="Whether consolidation was triggered")
    consolidation_result: Optional['TelemetryConsolidationResult'] = Field(None, description="Consolidation result if triggered")
    error: Optional[str] = Field(None, description="Main error if processing failed")

class TelemetryData(BaseModel):
    """Structured telemetry data."""
    metrics: Dict[str, Union[int, float]] = Field(default_factory=dict, description="Numeric metrics")
    events: Dict[str, str] = Field(default_factory=dict, description="Event data")
    timestamps: Dict[str, datetime] = Field(default_factory=dict, description="Timestamps")

class ResourceData(BaseModel):
    """Structured resource usage data."""
    llm: Optional[Dict[str, Union[int, float]]] = Field(None, description="LLM resource usage")
    memory: Optional[Dict[str, float]] = Field(None, description="Memory usage")
    compute: Optional[Dict[str, float]] = Field(None, description="Compute usage")

class BehavioralData(BaseModel):
    """Structured behavioral data (tasks/thoughts)."""
    data_type: str = Field(..., description="Type: task or thought")
    content: Dict[str, Union[str, int, float, bool, list, dict]] = Field(..., description="Behavioral content")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Additional metadata")

# UserProfile imported from system_context
# ChannelContext imported from system_context

class TelemetryConsolidationResult(BaseModel):
    """Result of memory consolidation."""
    status: str = Field(..., description="Consolidation status")
    grace_applied: int = Field(0, description="Number of grace applications")
    timestamp: str = Field(..., description="Consolidation timestamp")
    memories_consolidated: int = Field(0, description="Number of memories consolidated")
    errors: List[str] = Field(default_factory=list, description="Any errors during consolidation")

class TelemetryServiceStatus(BaseModel):
    """Status of the telemetry service."""
    healthy: bool = Field(..., description="Whether service is healthy")
    cached_metrics: int = Field(0, description="Number of metrics in cache")
    metric_types: List[str] = Field(default_factory=list, description="Types of metrics being tracked")
    memory_bus_available: bool = Field(False, description="Whether memory bus is available")
    last_consolidation: Optional[datetime] = Field(None, description="Last consolidation time")
    memory_mb: float = Field(0.0, description="Memory usage in MB")
    cache_size_mb: float = Field(0.0, description="Size of cached data in MB")
    custom_metrics: Optional[Dict[str, float]] = Field(None, description="Additional custom metrics")

class GraphQuery(BaseModel):
    """Query parameters for graph operations."""
    hours: int = Field(24, description="Hours of data to query")
    node_types: List[str] = Field(default_factory=list, description="Types of nodes to query")
    tags: Dict[str, str] = Field(default_factory=dict, description="Tags to filter by")
    limit: Optional[int] = Field(None, description="Maximum results to return")

class ServiceCapabilities(BaseModel):
    """Service capabilities declaration."""
    actions: List[str] = Field(..., description="Supported actions")
    features: List[str] = Field(..., description="Supported features")
    node_type: str = Field(..., description="Primary node type managed")
    version: str = Field("1.0.0", description="Service version")

class LLMUsageData(BaseModel):
    """Structured LLM usage data to replace Dict[str, Any]."""
    tokens_used: Optional[int] = Field(None, description="Total tokens used")
    tokens_input: Optional[int] = Field(None, description="Input tokens")
    tokens_output: Optional[int] = Field(None, description="Output tokens")
    cost_cents: Optional[float] = Field(None, description="Cost in cents")
    carbon_grams: Optional[float] = Field(None, description="Carbon emissions in grams")
    energy_kwh: Optional[float] = Field(None, description="Energy usage in kWh")
    model_used: Optional[str] = Field(None, description="Model name used")

class TelemetryKwargs(BaseModel):
    """Structured kwargs for telemetry operations."""
    handler_name: Optional[str] = Field(None, description="Handler name for the operation")
    trace_id: Optional[str] = Field(None, description="Trace ID for correlation")
    parent_id: Optional[str] = Field(None, description="Parent operation ID")
    user_id: Optional[str] = Field(None, description="User ID if applicable")
    channel_id: Optional[str] = Field(None, description="Channel ID if applicable")
    metadata: Dict[str, Union[str, int, float, bool]] = Field(
        default_factory=dict, description="Additional metadata"
    )


__all__ = [
    "TelemetrySnapshotResult",
    "TelemetryData",
    "ResourceData",
    "BehavioralData",
    "TelemetryConsolidationResult",
    "TelemetryServiceStatus",
    "GraphQuery",
    "ServiceCapabilities",
    "LLMUsageData",
    "TelemetryKwargs",
]
