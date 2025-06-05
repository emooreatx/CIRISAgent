from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, Union, List
from enum import Enum
from datetime import datetime, timezone

class FeedbackType(str, Enum):
    """Types of WA feedback."""
    IDENTITY_UPDATE = "identity_update"
    ENVIRONMENT_UPDATE = "environment_update" 
    MEMORY_CORRECTION = "memory_correction"
    DECISION_OVERRIDE = "decision_override"
    POLICY_CLARIFICATION = "policy_clarification"
    SYSTEM_DIRECTIVE = "system_directive"

class FeedbackSource(str, Enum):
    """Source of the feedback."""
    WISE_AUTHORITY = "wise_authority"
    HUMAN_OPERATOR = "human_operator"
    SYSTEM_MONITOR = "system_monitor"
    PEER_AGENT = "peer_agent"

class FeedbackDirective(BaseModel):
    """Specific directive within feedback."""
    action: FeedbackType  # "update", "delete", "add", "override", etc.
    target: FeedbackType  # What to act on
    data: Union[Dict[str, Any], str, List[Any]]
    reasoning: Optional[str] = None

class WiseAuthorityFeedback(BaseModel):
    """Structured feedback from WA on deferred decisions."""
    feedback_id: FeedbackType
    
    original_report_id: Optional[str] = None
    original_thought_id: Optional[str] = None
    original_task_id: Optional[str] = None
    
    feedback_type: FeedbackType
    feedback_source: FeedbackSource
    directives: List[FeedbackDirective] = Field(default_factory=list)
    
    summary: FeedbackType = ""
    detailed_reasoning: Optional[str] = None
    authority_confidence: FeedbackType = Field(default=1.0, ge=0.0, le=1.0)
    
    priority: FeedbackType = Field(default="normal")
    implementation_notes: Optional[str] = None
    
    created_at: FeedbackType = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: FeedbackType = "wise_authority"
    expires_at: Optional[str] = None
    
    processed: FeedbackType = False
    processed_at: Optional[str] = None
    processing_result: Optional[Dict[str, Any]] = None

class FeedbackMapping(BaseModel):
    """Maps feedback to original context for processing."""
    mapping_id: FeedbackType
    feedback_id: FeedbackType
    
    # Original context
    source_message_id: Optional[str] = None  # Discord message, etc.
    source_task_id: Optional[str] = None
    source_thought_id: Optional[str] = None
    
    # Transport context
    transport_type: FeedbackType  # "discord", "email", "api", etc.
    transport_data: Dict[str, Any] = Field(default_factory=dict)
    
    created_at: FeedbackType


class OptimizationVetoResult(BaseModel):
    """Result of the optimization veto guardrail."""

    decision: FeedbackType
    justification: FeedbackType
    entropy_reduction_ratio: FeedbackType
    affected_values: List[str] = Field(default_factory=list)
    confidence: FeedbackType = 1.0


class EpistemicHumilityResult(BaseModel):
    """Result of the epistemic humility check."""

    epistemic_certainty: FeedbackType
    identified_uncertainties: List[str] = Field(default_factory=list)
    reflective_justification: FeedbackType
    recommended_action: FeedbackType
