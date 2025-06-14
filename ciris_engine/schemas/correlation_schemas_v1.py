from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class ServiceCorrelationStatus(str, Enum):
    """Status values for service correlations."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"

class CorrelationType(str, Enum):
    """Types of correlations supported by the TSDB system."""
    SERVICE_INTERACTION = "service_interaction"
    
    METRIC_DATAPOINT = "metric_datapoint"
    LOG_ENTRY = "log_entry" 
    TRACE_SPAN = "trace_span"
    AUDIT_EVENT = "audit_event"
    
    METRIC_HOURLY_SUMMARY = "metric_hourly_summary"
    METRIC_DAILY_SUMMARY = "metric_daily_summary"
    LOG_HOURLY_SUMMARY = "log_hourly_summary"

class ServiceCorrelation(BaseModel):
    """Record correlating service requests and responses with TSDB capabilities."""
    # Existing fields
    correlation_id: str
    service_type: str
    handler_name: str
    action_type: str
    request_data: Optional[Dict[str, Any]] = None
    response_data: Optional[Dict[str, Any]] = None
    status: ServiceCorrelationStatus = ServiceCorrelationStatus.PENDING
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    # New TSDB fields
    correlation_type: CorrelationType = CorrelationType.SERVICE_INTERACTION
    timestamp: Optional[datetime] = None  # Indexed timestamp for time queries
    metric_name: Optional[str] = None  # For metric correlations
    metric_value: Optional[float] = None  # For metric correlations
    log_level: Optional[str] = None  # For log correlations
    trace_id: Optional[str] = None  # For distributed tracing
    span_id: Optional[str] = None  # For trace spans
    parent_span_id: Optional[str] = None  # For trace hierarchy
    tags: Dict[str, str] = Field(default_factory=dict)  # Flexible tagging
    retention_policy: str = "raw"  # raw, hourly_summary, daily_summary

__all__ = [
    "ServiceCorrelationStatus",
    "CorrelationType",
    "ServiceCorrelation",
]
