from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timezone
from enum import Enum

# Import shared enums from feedback_schemas_v1
from .feedback_schemas_v1 import FeedbackType, FeedbackSource, FeedbackDirective

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
