"""
Schemas for configuration feedback loop operations.

These replace all Dict[str, Any] usage in logic/infrastructure/sub_services/configuration_feedback_loop.py.
"""
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

from ciris_engine.schemas.services.graph_core import ConfigNodeType
from pydantic import Field

class PatternType(str, Enum):
    """Types of patterns we can detect."""
    TEMPORAL = "temporal"          # Time-based patterns
    FREQUENCY = "frequency"        # Usage frequency patterns
    PERFORMANCE = "performance"    # Performance optimization patterns
    ERROR = "error"               # Error/failure patterns
    USER_PREFERENCE = "user_preference"  # User interaction patterns

class PatternMetrics(BaseModel):
    """Metrics associated with a detected pattern."""
    occurrence_count: int = Field(0, description="Number of occurrences")
    average_value: float = Field(0.0, description="Average metric value")
    peak_value: float = Field(0.0, description="Peak metric value")
    time_range_hours: float = Field(24.0, description="Time range analyzed")
    data_points: int = Field(0, description="Number of data points")
    trend: str = Field("stable", description="Trend: increasing, decreasing, stable")
    metadata: dict = Field(default_factory=dict, description="Additional metrics")

class DetectedPattern(BaseModel):
    """A pattern detected from metrics/telemetry."""
    pattern_type: PatternType = Field(..., description="Type of pattern")
    pattern_id: str = Field(..., description="Unique pattern identifier")
    description: str = Field(..., description="Human-readable description")
    evidence_nodes: List[str] = Field(default_factory=list, description="Supporting evidence node IDs")
    confidence: float = Field(..., description="Confidence score 0-1")
    detected_at: datetime = Field(..., description="When pattern was detected")
    metrics: PatternMetrics = Field(..., description="Pattern metrics")

class ConfigurationUpdate(BaseModel):
    """A configuration update derived from patterns."""
    config_type: ConfigNodeType = Field(..., description="Type of configuration")
    update_type: str = Field(..., description="Update type: create, modify, delete")
    current_value: Optional[str] = Field(None, description="Current value (serialized)")
    new_value: Optional[str] = Field(None, description="New value (serialized)")
    reason: str = Field(..., description="Reason for update")
    pattern_id: str = Field(..., description="Pattern that triggered update")
    applied: bool = Field(False, description="Whether update was applied")
    applied_at: Optional[datetime] = Field(None, description="When update was applied")

class AnalysisResult(BaseModel):
    """Result of feedback loop analysis."""
    status: str = Field(..., description="Status: completed, not_due, error")
    patterns_detected: int = Field(0, description="Number of patterns detected")
    proposals_generated: int = Field(0, description="Number of proposals generated")
    adaptations_applied: int = Field(0, description="Number of adaptations applied")
    insights_stored: int = Field(0, description="Number of insights stored for agent introspection")
    timestamp: datetime = Field(..., description="Analysis timestamp")
    next_analysis_in: Optional[float] = Field(None, description="Seconds until next analysis")
    error: Optional[str] = Field(None, description="Error message if failed")

class ActionsByHour(BaseModel):
    """Actions grouped by hour of day."""
    hour: int = Field(..., description="Hour of day (0-23)")
    action_counts: Dict[str, int] = Field(default_factory=dict, description="Action counts by type")
    total_actions: int = Field(0, description="Total actions in hour")
    average_response_time_ms: float = Field(0.0, description="Average response time")

class ToolUsagePattern(BaseModel):
    """Pattern in tool usage."""
    tool_name: str = Field(..., description="Tool name")
    peak_hours: List[int] = Field(default_factory=list, description="Peak usage hours")
    total_uses: int = Field(0, description="Total uses in period")
    success_rate: float = Field(0.0, description="Success rate")
    average_execution_time_ms: float = Field(0.0, description="Average execution time")

class ResponseTimePattern(BaseModel):
    """Pattern in response times."""
    pattern_name: str = Field(..., description="Pattern identifier")
    slow_hours: List[int] = Field(default_factory=list, description="Hours with slow response")
    fast_hours: List[int] = Field(default_factory=list, description="Hours with fast response")
    variance: float = Field(0.0, description="Response time variance")
    recommendation: str = Field(..., description="Optimization recommendation")

class AdaptationProposal(BaseModel):
    """Proposed adaptation based on patterns."""
    proposal_id: str = Field(..., description="Unique proposal ID")
    pattern_ids: List[str] = Field(..., description="Patterns supporting this proposal")
    config_updates: List[ConfigurationUpdate] = Field(..., description="Proposed updates")
    expected_improvement: float = Field(..., description="Expected improvement percentage")
    risk_score: float = Field(..., description="Risk score 0-1")
    priority: str = Field("medium", description="Priority: low, medium, high")
    approved: bool = Field(False, description="Whether proposal is approved")

class LearningState(BaseModel):
    """Current state of the learning system."""
    patterns_learned: int = Field(0, description="Total patterns learned")
    successful_adaptations: List[str] = Field(default_factory=list, description="Successful adaptation IDs")
    failed_adaptations: List[str] = Field(default_factory=list, description="Failed adaptation IDs")
    success_rate: float = Field(0.0, description="Adaptation success rate")
    last_update: datetime = Field(..., description="Last learning update")

class PatternHistory(BaseModel):
    """Historical pattern tracking."""
    pattern_id: str = Field(..., description="Pattern ID")
    occurrences: List[datetime] = Field(default_factory=list, description="When pattern occurred")
    confidence_trend: List[float] = Field(default_factory=list, description="Confidence over time")
    adaptations_triggered: int = Field(0, description="Number of adaptations from this pattern")