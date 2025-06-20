"""WiseAuthority context schemas for type-safe WA operations."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class GuidanceContext(BaseModel):
    """Context for requesting guidance from Wise Authority."""
    
    thought_id: str = Field(..., description="ID of the thought requesting guidance")
    task_id: str = Field(..., description="ID of the associated task")
    question: str = Field(..., description="The question or dilemma requiring guidance")
    ethical_considerations: Optional[List[str]] = Field(None, description="Ethical factors to consider")
    domain_context: Optional[Dict[str, str]] = Field(None, description="Domain-specific context")
    
    class Config:
        extra = "forbid"  # No additional fields allowed


class DeferralContext(BaseModel):
    """Context for deferral operations."""
    
    thought_id: str = Field(..., description="ID of the thought being deferred")
    task_id: str = Field(..., description="ID of the associated task")
    reason: str = Field(..., description="Reason for deferral")
    defer_until: Optional[str] = Field(None, description="ISO timestamp when to reconsider")
    priority: Optional[str] = Field(None, description="Priority level for later consideration")
    metadata: Optional[Dict[str, str]] = Field(None, description="Additional deferral metadata")
    
    class Config:
        extra = "forbid"  # No additional fields allowed