from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, Union, List
from enum import Enum

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
    action: str  # "update", "delete", "add", "override", etc.
    target: str  # What to act on
    data: Union[Dict[str, Any], str, List[Any]]
    reasoning: Optional[str] = None

class WiseAuthorityFeedback(BaseModel):
    """Structured feedback from WA on deferred decisions."""
    feedback_id: str
    
    # Reference to original deferral
    original_report_id: Optional[str] = None
    original_thought_id: Optional[str] = None
    original_task_id: Optional[str] = None
    
    # Feedback content  
    feedback_type: FeedbackType
    feedback_source: FeedbackSource
    directives: List[FeedbackDirective] = Field(default_factory=list)
    
    # Context and reasoning
    summary: str
    detailed_reasoning: Optional[str] = None
    authority_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    
    # Implementation guidance
    priority: str = Field(default="normal")  # low, normal, high, critical
    implementation_notes: Optional[str] = None
    
    # Metadata
    created_at: str
    created_by: str  # WA identifier
    expires_at: Optional[str] = None
    
    # Processing status
    processed: bool = False
    processed_at: Optional[str] = None
    processing_result: Optional[Dict[str, Any]] = None

class FeedbackMapping(BaseModel):
    """Maps feedback to original context for processing."""
    mapping_id: str
    feedback_id: str
    
    # Original context
    source_message_id: Optional[str] = None  # Discord message, etc.
    source_task_id: Optional[str] = None
    source_thought_id: Optional[str] = None
    
    # Transport context
    transport_type: str  # "discord", "email", "api", etc.
    transport_data: Dict[str, Any] = Field(default_factory=dict)
    
    created_at: str


class OptimizationVetoResult(BaseModel):
    """Result of the optimization veto guardrail."""

    decision: str
    justification: str
    entropy_reduction_ratio: float
    affected_values: List[str] = Field(default_factory=list)
    confidence: float = 1.0


class EpistemicHumilityResult(BaseModel):
    """Result of the epistemic humility check."""

    epistemic_certainty: str
    identified_uncertainties: List[str] = Field(default_factory=list)
    reflective_justification: str
    recommended_action: str
