from pydantic import BaseModel
from typing import Optional, Dict, Any

class AuditLogEntry(BaseModel):
    """Schema for audit log entries."""
    event_id: str
    event_timestamp: str  # ISO8601
    event_type: str
    originator_id: str
    target_id: Optional[str] = None
    event_summary: str
    event_payload: Optional[Dict[str, Any]] = None
    
    # Additional metadata
    agent_profile: Optional[str] = None
    round_number: Optional[int] = None
    thought_id: Optional[str] = None
    task_id: Optional[str] = None
