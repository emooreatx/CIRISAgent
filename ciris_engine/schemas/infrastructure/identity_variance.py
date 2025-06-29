"""
Schemas for identity variance monitoring operations.

These replace all Dict[str, Any] usage in logic/infrastructure/sub_services/identity_variance_monitor.py.
"""
from typing import Dict, List, Optional, Set
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

class VarianceImpact(str, Enum):
    """Impact levels for different types of changes (not used in variance calculation)."""
    CRITICAL = "critical"    # Core purpose/ethics changes
    HIGH = "high"           # Capabilities/trust changes
    MEDIUM = "medium"       # Behavioral patterns
    LOW = "low"            # Preferences/templates

class IdentityDiff(BaseModel):
    """Represents a difference between baseline and current identity."""
    node_id: str = Field(..., description="Node ID where difference found")
    diff_type: str = Field(..., description="Type of difference: added, removed, modified")
    impact: VarianceImpact = Field(..., description="Impact level of the change")
    baseline_value: Optional[str] = Field(None, description="Value in baseline (serialized)")
    current_value: Optional[str] = Field(None, description="Current value (serialized)")
    description: str = Field(..., description="Human-readable description of difference")

class VarianceReport(BaseModel):
    """Complete variance analysis report."""
    timestamp: datetime = Field(..., description="When analysis was performed")
    baseline_snapshot_id: str = Field(..., description="ID of baseline snapshot")
    current_snapshot_id: str = Field(..., description="ID of current snapshot")
    total_variance: float = Field(..., description="Total variance percentage (simple count/total)")
    differences: List[IdentityDiff] = Field(default_factory=list, description="List of differences found")
    requires_wa_review: bool = Field(..., description="Whether WA review is required")
    recommendations: List[str] = Field(default_factory=list, description="Recommended actions")

# IdentitySnapshot moved to schemas/services/nodes.py as TypedGraphNode

class VarianceAnalysis(BaseModel):
    """Detailed variance analysis between snapshots."""
    baseline_nodes: Set[str] = Field(default_factory=set, description="Node IDs in baseline")
    current_nodes: Set[str] = Field(default_factory=set, description="Node IDs in current")
    added_nodes: Set[str] = Field(default_factory=set, description="Nodes added since baseline")
    removed_nodes: Set[str] = Field(default_factory=set, description="Nodes removed since baseline")
    modified_nodes: Set[str] = Field(default_factory=set, description="Nodes modified since baseline")
    variance_scores: Dict[str, float] = Field(default_factory=dict, description="Variance score by node")
    impact_counts: Dict[VarianceImpact, int] = Field(default_factory=dict, description="Count of changes by impact")

class WAReviewRequest(BaseModel):
    """Request for WA review of identity variance."""
    request_id: str = Field(..., description="Unique request ID")
    timestamp: datetime = Field(..., description="When request was made")
    current_variance: float = Field(..., description="Current variance percentage")
    variance_report: VarianceReport = Field(..., description="Full variance report")
    critical_changes: List[IdentityDiff] = Field(default_factory=list, description="Critical changes requiring review")
    proposed_actions: List[str] = Field(default_factory=list, description="Proposed corrective actions")
    urgency: str = Field("high", description="Review urgency level")

class VarianceCheckMetadata(BaseModel):
    """Metadata for variance check operations."""
    handler_name: str = Field("identity_variance_monitor", description="Handler performing check")
    check_type: str = Field(..., description="Type of check: scheduled, forced, triggered")
    check_reason: Optional[str] = Field(None, description="Reason for check if triggered")
    previous_check: Optional[datetime] = Field(None, description="Previous check timestamp")
    baseline_established: datetime = Field(..., description="When baseline was established")
