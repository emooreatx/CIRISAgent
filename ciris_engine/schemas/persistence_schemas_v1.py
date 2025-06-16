"""
Persistence-specific schemas for type-safe database operations.

These schemas ensure all data flowing through the persistence layer is properly typed.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field

from .foundational_schemas_v1 import HandlerActionType
from .correlation_schemas_v1 import ServiceCorrelationStatus, CorrelationType


class DeferralPackage(BaseModel):
    """Type-safe container for deferral report package data."""
    defer_until: Optional[str] = Field(None, description="ISO timestamp for deferred execution")
    reason: Optional[str] = Field(None, description="Reason for deferral")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")
    
    class Config:
        extra = "allow"  # Allow additional fields for extensibility


class DeferralReportContext(BaseModel):
    """Type-safe response for deferral report queries."""
    task_id: str = Field(..., description="Associated task ID")
    thought_id: str = Field(..., description="Associated thought ID")
    package: Optional[DeferralPackage] = Field(None, description="Deferral package data")


class CorrelationUpdateRequest(BaseModel):
    """Type-safe request for updating correlations."""
    correlation_id: str = Field(..., description="Correlation to update")
    response_data: Optional[Dict[str, Any]] = Field(None, description="Response data to store")
    status: Optional[ServiceCorrelationStatus] = Field(None, description="New status")
    metric_value: Optional[float] = Field(None, description="Metric value if applicable")
    tags: Optional[Dict[str, str]] = Field(None, description="Tags to update")


class MetricsQuery(BaseModel):
    """Type-safe query parameters for metrics timeseries."""
    metric_name: str = Field(..., description="Name of the metric to query")
    start_time: Optional[datetime] = Field(None, description="Start of time range")
    end_time: Optional[datetime] = Field(None, description="End of time range")
    tags: Optional[Dict[str, str]] = Field(default_factory=dict, description="Filter tags")
    aggregation: Optional[str] = Field("avg", description="Aggregation method: avg, sum, max, min")
    interval: Optional[str] = Field("1h", description="Time bucket interval")


class IdentityContext(BaseModel):
    """Type-safe identity context for processing."""
    agent_name: str = Field(..., description="Agent identifier")
    agent_role: str = Field(..., description="Agent role description")
    description: str = Field(..., description="Agent description")
    domain_specific_knowledge: Dict[str, Any] = Field(default_factory=dict)
    permitted_actions: List[HandlerActionType] = Field(..., description="Allowed actions as enums")
    restricted_capabilities: List[str] = Field(default_factory=list)
    dsdma_prompt_template: Optional[str] = Field(None)
    csdma_overrides: Dict[str, Any] = Field(default_factory=dict)
    action_selection_pdma_overrides: Dict[str, Any] = Field(default_factory=dict)


class ThoughtSummary(BaseModel):
    """Type-safe thought summary for recent thoughts queries."""
    thought_id: str
    thought_type: str
    status: str
    created_at: str
    content: str
    source_task_id: str


class TaskSummaryInfo(BaseModel):
    """Type-safe task summary for queries returning task info."""
    task_id: str
    description: str
    status: str
    created_at: str
    priority: Optional[int] = None
    channel_id: Optional[str] = None