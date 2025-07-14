"""
Schemas for TSDB Consolidation data structures.

These schemas replace Dict[str, Any] usage in TSDB consolidation service,
ensuring type safety for all consolidation operations.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ServiceInteractionData(BaseModel):
    """Data structure for service interaction consolidation."""
    
    correlation_id: str = Field(..., description="Unique correlation ID")
    action_type: str = Field(..., description="Type of action performed")
    service_type: str = Field(..., description="Type of service")
    timestamp: datetime = Field(..., description="When the interaction occurred")
    channel_id: str = Field(default="unknown", description="Channel where interaction occurred")
    
    # Request data fields
    request_data: Optional[Dict[str, Any]] = Field(None, description="Raw request data")
    author_id: Optional[str] = Field(None, description="ID of the message author")
    author_name: Optional[str] = Field(None, description="Name of the message author")
    content: Optional[str] = Field(None, description="Message content")
    
    # Response data fields
    response_data: Optional[Dict[str, Any]] = Field(None, description="Raw response data")
    execution_time_ms: float = Field(default=0.0, description="Execution time in milliseconds")
    success: bool = Field(default=True, description="Whether the interaction succeeded")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    # Context data
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context data")


class MetricCorrelationData(BaseModel):
    """Data structure for metric correlation consolidation."""
    
    correlation_id: str = Field(..., description="Unique correlation ID")
    metric_name: str = Field(..., description="Name of the metric")
    value: float = Field(..., description="Metric value")
    timestamp: datetime = Field(..., description="When the metric was recorded")
    
    # Request/response data
    request_data: Optional[Dict[str, Any]] = Field(None, description="Raw request data")
    response_data: Optional[Dict[str, Any]] = Field(None, description="Raw response data")
    
    # Tags and metadata
    tags: Dict[str, str] = Field(default_factory=dict, description="Metric tags")
    source: str = Field(default="correlation", description="Source of the metric (correlation or graph_node)")
    
    # Additional fields
    unit: Optional[str] = Field(None, description="Unit of measurement")
    aggregation_type: Optional[str] = Field(None, description="Type of aggregation (sum, avg, max, etc)")


class TraceSpanData(BaseModel):
    """Data structure for trace span consolidation."""
    
    trace_id: str = Field(..., description="Trace ID")
    span_id: str = Field(..., description="Span ID")
    parent_span_id: Optional[str] = Field(None, description="Parent span ID")
    timestamp: datetime = Field(..., description="When the span started")
    duration_ms: float = Field(default=0.0, description="Span duration in milliseconds")
    
    # Span metadata
    operation_name: str = Field(..., description="Name of the operation")
    service_name: str = Field(..., description="Service that created the span")
    status: str = Field(default="ok", description="Span status (ok, error, etc)")
    
    # Tags and context
    tags: Dict[str, Any] = Field(default_factory=dict, description="Span tags")
    task_id: Optional[str] = Field(None, description="Associated task ID")
    thought_id: Optional[str] = Field(None, description="Associated thought ID")
    component_type: Optional[str] = Field(None, description="Component type that created the span")
    
    # Error information
    error: bool = Field(default=False, description="Whether the span had an error")
    error_message: Optional[str] = Field(None, description="Error message if any")
    error_type: Optional[str] = Field(None, description="Type of error")
    
    # Performance data
    latency_ms: Optional[float] = Field(None, description="Operation latency")
    resource_usage: Dict[str, float] = Field(default_factory=dict, description="Resource usage metrics")


class TaskCorrelationData(BaseModel):
    """Data structure for task correlation consolidation."""
    
    task_id: str = Field(..., description="Unique task ID")
    status: str = Field(..., description="Task status")
    created_at: datetime = Field(..., description="When task was created")
    updated_at: datetime = Field(..., description="When task was last updated")
    
    # Task metadata
    channel_id: Optional[str] = Field(None, description="Channel where task originated")
    user_id: Optional[str] = Field(None, description="User who created the task")
    task_type: Optional[str] = Field(None, description="Type of task")
    
    # Execution data
    retry_count: int = Field(default=0, description="Number of retries")
    duration_ms: float = Field(default=0.0, description="Total task duration")
    
    # Thoughts and handlers
    thoughts: List[Dict[str, Any]] = Field(default_factory=list, description="Associated thoughts")
    handlers_used: List[str] = Field(default_factory=list, description="Handlers that processed this task")
    final_handler: Optional[str] = Field(None, description="Final handler that completed the task")
    
    # Outcome data
    success: bool = Field(default=True, description="Whether task succeeded")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    result_summary: Optional[str] = Field(None, description="Summary of task result")
    
    # Additional context
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional task metadata")


class ConversationEntry(BaseModel):
    """Single entry in a conversation."""
    
    timestamp: Optional[str] = Field(None, description="ISO formatted timestamp")
    correlation_id: str = Field(..., description="Correlation ID")
    action_type: str = Field(..., description="Type of action")
    content: str = Field(default="", description="Message content")
    author_id: Optional[str] = Field(None, description="Author ID")
    author_name: Optional[str] = Field(None, description="Author name")
    execution_time_ms: float = Field(default=0.0, description="Execution time")
    success: bool = Field(default=True, description="Whether action succeeded")


class ParticipantData(BaseModel):
    """Data about a conversation participant."""
    
    message_count: int = Field(default=0, description="Number of messages")
    channels: List[str] = Field(default_factory=list, description="Channels participated in")
    author_name: Optional[str] = Field(None, description="Participant name")


class TSDBPeriodSummary(BaseModel):
    """Summary data for a TSDB consolidation period."""
    
    # Metrics data
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Aggregated metrics for the period")
    
    # Resource usage totals
    total_tokens: int = Field(default=0, description="Total tokens used in period")
    total_cost_cents: int = Field(default=0, description="Total cost in cents for period")
    total_carbon_grams: float = Field(default=0.0, description="Total carbon emissions in grams")
    total_energy_kwh: float = Field(default=0.0, description="Total energy usage in kWh")
    
    # Action counts
    action_counts: Dict[str, int] = Field(default_factory=dict, description="Count of actions by type")
    source_node_count: int = Field(default=0, description="Number of source nodes consolidated")
    
    # Period information
    period_start: str = Field(..., description="ISO formatted period start time")
    period_end: str = Field(..., description="ISO formatted period end time")
    period_label: str = Field(..., description="Human-readable period label")
    
    # Consolidated data lists
    conversations: List[Dict[str, Any]] = Field(default_factory=list, description="Consolidated conversation data")
    traces: List[Dict[str, Any]] = Field(default_factory=list, description="Consolidated trace data")
    audits: List[Dict[str, Any]] = Field(default_factory=list, description="Consolidated audit data")
    tasks: List[Dict[str, Any]] = Field(default_factory=list, description="Consolidated task data")
    memories: List[Dict[str, Any]] = Field(default_factory=list, description="Consolidated memory data")


__all__ = [
    "ServiceInteractionData",
    "MetricCorrelationData", 
    "TraceSpanData",
    "TaskCorrelationData",
    "ConversationEntry",
    "ParticipantData",
    "TSDBPeriodSummary"
]