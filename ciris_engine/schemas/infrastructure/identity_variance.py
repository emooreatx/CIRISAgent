"""
Schemas for identity variance monitoring operations.

These replace all Dict[str, Any] usage in logic/infrastructure/sub_services/identity_variance_monitor.py.
"""
from typing import Dict, List, Optional, Set
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import Field

class VarianceImpact(str, Enum):
    """Impact levels for different types of changes."""
    CRITICAL = "critical"    # 5x weight - Core purpose/ethics changes
    HIGH = "high"           # 3x weight - Capabilities/trust changes  
    MEDIUM = "medium"       # 2x weight - Behavioral patterns
    LOW = "low"            # 1x weight - Preferences/templates

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
    total_variance: float = Field(..., description="Total variance percentage")
    variance_by_impact: Dict[VarianceImpact, float] = Field(..., description="Variance breakdown by impact")
    differences: List[IdentityDiff] = Field(default_factory=list, description="List of differences found")
    requires_wa_review: bool = Field(..., description="Whether WA review is required")
    recommendations: List[str] = Field(default_factory=list, description="Recommended actions")

class IdentitySnapshot(BaseModel):
    """Snapshot of identity state at a point in time."""
    snapshot_id: str = Field(..., description="Unique snapshot ID")
    timestamp: datetime = Field(..., description="When snapshot was taken")
    agent_id: str = Field(..., description="Agent ID")
    identity_hash: str = Field(..., description="Identity hash")
    core_purpose: str = Field(..., description="Core purpose description")
    role: str = Field(..., description="Role description")
    permitted_actions: List[str] = Field(default_factory=list, description="Permitted action names")
    restricted_capabilities: List[str] = Field(default_factory=list, description="Restricted capabilities")
    ethical_boundaries: List[str] = Field(default_factory=list, description="Ethical boundaries")
    trust_parameters: Dict[str, str] = Field(default_factory=dict, description="Trust parameters")
    behavioral_patterns: Dict[str, float] = Field(default_factory=dict, description="Behavioral pattern scores")
    config_preferences: Dict[str, str] = Field(default_factory=dict, description="Configuration preferences")
    attributes: dict = Field(default_factory=dict, description="Additional attributes")

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