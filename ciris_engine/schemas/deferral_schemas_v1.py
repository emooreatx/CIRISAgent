from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timezone
from enum import Enum

class DeferralReason(str, Enum):
    """Standard deferral reason codes."""
    GUARDRAIL_FAILURE = "guardrail_failure"
    MAX_PONDER_REACHED = "max_ponder_reached" 
    CHANNEL_POLICY_UPDATE = "channel_policy_update"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    ETHICAL_CONCERN = "ethical_concern"
    SYSTEM_ERROR = "system_error"
    WA_REVIEW_REQUIRED = "wa_review_required"
    MEMORY_CONFLICT = "memory_conflict"
    UNKNOWN = "unknown"

class DeferralPackage(BaseModel):
    """Complete context package for deferred decisions."""
    # Core identifiers
    thought_id: str
    task_id: str
    deferral_reason: DeferralReason
    reason_description: str
    
    # Decision context
    thought_content: str
    task_description: Optional[str] = None
    
    # DMA results that led to deferral
    ethical_assessment: Optional[Dict[str, Any]] = None
    csdma_assessment: Optional[Dict[str, Any]] = None
    dsdma_assessment: Optional[Dict[str, Any]] = None
    
    # System context at time of deferral
    user_profiles: Optional[Dict[str, Any]] = None
    system_snapshot: Optional[Dict[str, Any]] = None
    
    # Processing history
    ponder_history: List[str] = Field(default_factory=list)
    action_history: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class DeferralReport(BaseModel):
    """Deferral report for transmission to WA."""
    report_id: str
    package: DeferralPackage
    target_wa_identifier: str  # Could be Discord user, email, etc.
    urgency_level: str = Field(default="normal")  # low, normal, high, critical
    
    # Transport metadata (set by adapters)
    transport_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    
    # Status tracking
    delivered: bool = False
    delivered_at: Optional[str] = None
    response_received: bool = False
    response_at: Optional[str] = None

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
    summary: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str = "wise_authority"
