"""
Self-configuration service schemas.

Replaces Dict[str, Any] in self-configuration operations.
"""
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from enum import Enum
from pydantic import Field

class AdaptationState(str, Enum):
    """Current state of the self-configuration system."""
    LEARNING = "learning"          # Gathering data, no changes yet
    PROPOSING = "proposing"        # Actively proposing adaptations
    ADAPTING = "adapting"          # Applying approved changes
    STABILIZING = "stabilizing"    # Waiting for changes to settle
    REVIEWING = "reviewing"        # Under WA review for variance

class ProcessSnapshotResult(BaseModel):
    """Result of processing a system snapshot for adaptation."""
    patterns_detected: int = Field(0, description="Number of patterns detected")
    proposals_generated: int = Field(0, description="Number of proposals generated")
    changes_applied: int = Field(0, description="Number of changes applied")
    variance_percent: float = Field(0.0, description="Current variance from baseline")
    requires_review: bool = Field(False, description="Whether WA review is required")
    error: Optional[str] = Field(None, description="Error message if processing failed")

class AdaptationCycleResult(BaseModel):
    """Result of running an adaptation cycle."""
    cycle_id: str = Field(..., description="Unique cycle identifier")
    state: AdaptationState = Field(..., description="Current adaptation state")
    started_at: datetime = Field(..., description="When cycle started")
    completed_at: Optional[datetime] = Field(None, description="When cycle completed")
    
    # Pattern detection
    patterns_detected: int = Field(0, description="Number of patterns found")
    pattern_types: List[str] = Field(default_factory=list, description="Types of patterns")
    
    # Proposals
    proposals_generated: int = Field(0, description="Number of proposals created")
    proposals_approved: int = Field(0, description="Number of proposals approved")
    proposals_rejected: int = Field(0, description="Number of proposals rejected")
    
    # Changes
    changes_applied: int = Field(0, description="Number of changes applied")
    rollbacks_performed: int = Field(0, description="Number of rollbacks")
    
    # Variance
    variance_before: float = Field(0.0, description="Variance before cycle")
    variance_after: float = Field(0.0, description="Variance after cycle")
    
    # Outcome
    success: bool = Field(True, description="Whether cycle succeeded")
    requires_review: bool = Field(False, description="Whether WA review needed")
    error: Optional[str] = Field(None, description="Error if cycle failed")

class CycleEventData(BaseModel):
    """Data for adaptation cycle events."""
    event_type: str = Field(..., description="Type of event")
    cycle_id: str = Field(..., description="Associated cycle ID")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Event-specific data
    patterns: Optional[List[str]] = Field(None, description="Patterns for detection events")
    proposals: Optional[List[str]] = Field(None, description="Proposals for proposal events")
    changes: Optional[List[str]] = Field(None, description="Changes for change events")
    variance: Optional[float] = Field(None, description="Variance for variance events")
    
    # Additional context
    metadata: Dict[str, Union[str, int, float, bool]] = Field(
        default_factory=dict, description="Additional event metadata"
    )

class AdaptationStatus(BaseModel):
    """Current status of the adaptation system."""
    is_active: bool = Field(..., description="Whether adaptation is active")
    current_state: AdaptationState = Field(..., description="Current state")
    cycles_completed: int = Field(..., description="Total cycles completed")
    last_cycle_at: Optional[datetime] = Field(None, description="Last cycle time")
    
    # Current metrics
    current_variance: float = Field(0.0, description="Current variance from baseline")
    patterns_in_buffer: int = Field(0, description="Patterns awaiting processing")
    pending_proposals: int = Field(0, description="Proposals awaiting approval")
    
    # Performance
    average_cycle_duration_seconds: float = Field(0.0, description="Average cycle time")
    total_changes_applied: int = Field(0, description="Total changes ever applied")
    rollback_rate: float = Field(0.0, description="Percentage of changes rolled back")
    
    # Identity tracking
    identity_stable: bool = Field(True, description="Whether identity is stable")
    time_since_last_change: Optional[float] = Field(None, description="Seconds since last change")
    
    # Review status
    under_review: bool = Field(False, description="Whether under WA review")
    review_reason: Optional[str] = Field(None, description="Why review was triggered")

class ReviewOutcome(BaseModel):
    """Outcome of WA review process."""
    review_id: str = Field(..., description="Review identifier")
    reviewer_id: str = Field(..., description="WA reviewer identifier")
    decision: str = Field(..., description="approve, reject, or modify")
    
    # Approved changes
    approved_changes: List[str] = Field(default_factory=list, description="Changes approved")
    rejected_changes: List[str] = Field(default_factory=list, description="Changes rejected")
    
    # Modifications
    modified_proposals: Dict[str, str] = Field(
        default_factory=dict, description="Proposals with modifications"
    )
    
    # Guidance
    feedback: Optional[str] = Field(None, description="Review feedback")
    new_constraints: List[str] = Field(default_factory=list, description="New constraints added")
    
    # Actions
    resume_adaptation: bool = Field(True, description="Whether to resume adaptation")
    new_variance_limit: Optional[float] = Field(None, description="New variance limit if changed")

# ========== New Schemas for Enhanced Protocol ==========

class AgentIdentityRoot(BaseModel):
    """Root identity configuration for baseline establishment."""
    identity_id: str = Field(..., description="Unique identity identifier")
    core_values: List[str] = Field(..., description="Core ethical values")
    capabilities: List[str] = Field(..., description="Core capabilities")
    behavioral_constraints: List[str] = Field(..., description="Behavioral boundaries")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConfigurationChange(BaseModel):
    """A proposed or applied configuration change."""
    change_id: str = Field(..., description="Unique change identifier")
    scope: str = Field(..., description="Scope: LOCAL, ENVIRONMENT, IDENTITY, COMMUNITY")
    target_path: str = Field(..., description="Configuration path to change")
    old_value: Optional[Union[str, int, float, bool, List, Dict]] = Field(None)
    new_value: Union[str, int, float, bool, List, Dict] = Field(...)
    estimated_variance_impact: float = Field(..., description="Estimated variance %")
    confidence_score: float = Field(..., description="Confidence in this change")
    reason: str = Field(..., description="Why this change is proposed")
    status: str = Field("proposed", description="proposed, approved, applied, rolled_back")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    applied_at: Optional[datetime] = Field(None)

class ChangeApprovalResult(BaseModel):
    """Result of approving configuration changes."""
    approved_count: int = Field(0, description="Number of changes approved")
    rejected_count: int = Field(0, description="Number of changes rejected")
    applied_changes: List[str] = Field(default_factory=list, description="Change IDs applied")
    total_variance_impact: float = Field(0.0, description="Total variance from changes")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")

class RollbackResult(BaseModel):
    """Result of rolling back configuration changes."""
    rollback_count: int = Field(0, description="Number of changes rolled back")
    successful_rollbacks: List[str] = Field(default_factory=list, description="Successfully rolled back")
    failed_rollbacks: List[str] = Field(default_factory=list, description="Failed to rollback")
    variance_restored: float = Field(0.0, description="Variance % restored")
    errors: List[str] = Field(default_factory=list, description="Errors during rollback")

class ObservabilitySignal(BaseModel):
    """A signal from observability sources."""
    signal_type: str = Field(..., description="trace, log, metric, incident, security")
    timestamp: datetime = Field(..., description="When signal occurred")
    severity: str = Field("info", description="info, warning, error, critical")
    source: str = Field(..., description="Source service or component")
    details: Dict[str, Union[str, int, float, bool, List]] = Field(default_factory=dict)

class AdaptationOpportunity(BaseModel):
    """An opportunity for system adaptation."""
    opportunity_id: str = Field(..., description="Unique identifier")
    trigger_signals: List[ObservabilitySignal] = Field(..., description="Signals that triggered this")
    proposed_changes: List[ConfigurationChange] = Field(..., description="Proposed changes")
    expected_improvement: Dict[str, float] = Field(..., description="Expected improvements")
    risk_assessment: str = Field(..., description="Risk level: low, medium, high")
    priority: int = Field(0, description="Priority score")

class ObservabilityAnalysis(BaseModel):
    """Analysis of all observability signals for a time window."""
    window_start: datetime = Field(..., description="Analysis window start")
    window_end: datetime = Field(..., description="Analysis window end")
    
    # Signal counts
    total_signals: int = Field(0, description="Total signals analyzed")
    signals_by_type: Dict[str, int] = Field(default_factory=dict)
    
    # Patterns found
    patterns_detected: List[str] = Field(default_factory=list, description="Pattern types found")
    anomalies_detected: List[str] = Field(default_factory=list, description="Anomalies found")
    
    # Opportunities
    adaptation_opportunities: List[AdaptationOpportunity] = Field(default_factory=list)
    
    # Health assessment
    system_health_score: float = Field(100.0, description="Overall health 0-100")
    component_health: Dict[str, float] = Field(default_factory=dict)

class AdaptationImpact(BaseModel):
    """Measured impact of an adaptation."""
    dimension: str = Field(..., description="Impact dimension measured")
    baseline_value: float = Field(..., description="Value before adaptation")
    current_value: float = Field(..., description="Value after adaptation")
    improvement_percent: float = Field(..., description="Percentage improvement")
    measurement_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AdaptationEffectiveness(BaseModel):
    """Overall effectiveness of an adaptation across all dimensions."""
    adaptation_id: str = Field(..., description="Adaptation being measured")
    measurement_period_hours: int = Field(24, description="Measurement period")
    
    # Impact by dimension
    performance_impact: Optional[AdaptationImpact] = Field(None)
    error_impact: Optional[AdaptationImpact] = Field(None)
    resource_impact: Optional[AdaptationImpact] = Field(None)
    stability_impact: Optional[AdaptationImpact] = Field(None)
    user_satisfaction_impact: Optional[AdaptationImpact] = Field(None)
    
    # Overall assessment
    overall_effectiveness: float = Field(0.0, description="Overall effectiveness score")
    recommendation: str = Field(..., description="keep, modify, rollback")

class PatternRecord(BaseModel):
    """A learned adaptation pattern."""
    pattern_id: str = Field(..., description="Unique pattern identifier")
    trigger_conditions: List[ObservabilitySignal] = Field(..., description="What triggers this")
    successful_applications: int = Field(0, description="Times successfully applied")
    failed_applications: int = Field(0, description="Times failed")
    average_improvement: float = Field(0.0, description="Average improvement %")
    confidence_score: float = Field(0.0, description="Confidence in pattern")
    last_applied: Optional[datetime] = Field(None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PatternLibrarySummary(BaseModel):
    """Summary of the pattern library."""
    total_patterns: int = Field(0, description="Total patterns in library")
    high_confidence_patterns: int = Field(0, description="Patterns with >70% confidence")
    recently_used_patterns: int = Field(0, description="Used in last 30 days")
    most_effective_patterns: List[PatternRecord] = Field(default_factory=list)
    pattern_categories: Dict[str, int] = Field(default_factory=dict)

class ServiceImprovementReport(BaseModel):
    """Comprehensive service improvement report."""
    report_period_start: datetime = Field(..., description="Report period start")
    report_period_end: datetime = Field(..., description="Report period end")
    
    # Adaptation summary
    total_adaptations: int = Field(0, description="Total adaptations in period")
    successful_adaptations: int = Field(0, description="Successful adaptations")
    rolled_back_adaptations: int = Field(0, description="Adaptations rolled back")
    
    # Impact summary
    average_performance_improvement: float = Field(0.0, description="Avg performance gain %")
    error_rate_reduction: float = Field(0.0, description="Error rate reduction %")
    resource_efficiency_gain: float = Field(0.0, description="Resource efficiency gain %")
    
    # Variance tracking
    starting_variance: float = Field(0.0, description="Variance at period start")
    ending_variance: float = Field(0.0, description="Variance at period end")
    peak_variance: float = Field(0.0, description="Peak variance in period")
    
    # Top improvements
    top_improvements: List[Dict[str, Union[str, float]]] = Field(default_factory=list)
    
    # Recommendations
    recommendations: List[str] = Field(default_factory=list, description="Future recommendations")

# Re-export SystemSnapshot from runtime context
from ciris_engine.schemas.runtime.system_context import SystemSnapshot

__all__ = [
    "AdaptationState",
    "ProcessSnapshotResult", 
    "AdaptationCycleResult",
    "CycleEventData",
    "AdaptationStatus",
    "ReviewOutcome",
    "AgentIdentityRoot",
    "ExperienceProcessingResult",
    "ConfigurationChange",
    "ChangeApprovalResult",
    "RollbackResult",
    "ObservabilitySignal",
    "AdaptationOpportunity",
    "ObservabilityAnalysis",
    "AdaptationImpact",
    "AdaptationEffectiveness",
    "PatternRecord",
    "PatternLibrarySummary",
    "ServiceImprovementReport",
    "SystemSnapshot"
]