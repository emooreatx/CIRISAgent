"""Audit schemas for WA operations."""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class WAAuditEventType(str, Enum):
    """Types of WA audit events."""
    # WA lifecycle
    WA_CREATED = "wa_created"
    WA_AUTO_MINTED = "wa_auto_minted"
    WA_PROMOTED = "wa_promoted"
    WA_REVOKED = "wa_revoked"
    WA_KEY_ROTATED = "wa_key_rotated"
    
    # Authentication
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILED = "auth_failed"
    TOKEN_ISSUED = "token_issued"
    TOKEN_REFRESH = "token_refresh"
    
    # OAuth
    OAUTH_LINKED = "oauth_linked"
    OAUTH_UNLINKED = "oauth_unlinked"
    
    # Veilid
    VEILID_LINKED = "veilid_linked"
    VEILID_UNLINKED = "veilid_unlinked"


class WAAuditEvent(BaseModel):
    """WA audit event record."""
    event_id: str = Field(..., description="Unique event ID")
    event_type: WAAuditEventType
    timestamp: datetime
    
    # Actor information
    actor_wa_id: Optional[str] = Field(None, description="WA performing the action")
    actor_ip: Optional[str] = Field(None, description="IP address if applicable")
    
    # Target information
    target_wa_id: Optional[str] = Field(None, description="WA being acted upon")
    
    # Event details
    details: Dict[str, Any] = Field(default_factory=dict)
    
    # Outcome
    success: bool = True
    error_message: Optional[str] = None
    
    # Cryptographic proof
    event_hash: Optional[str] = Field(None, description="SHA256 of event data")
    signature: Optional[str] = Field(None, description="Signature from actor WA")