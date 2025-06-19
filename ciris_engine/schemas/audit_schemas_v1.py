from pydantic import BaseModel
from typing import Optional, Dict, Any
from enum import Enum


class AuditEventType(str, Enum):
    """Types of audit events."""
    HANDLER_ACTION_SPEAK = "handler_action_speak"
    HANDLER_ACTION_MEMORIZE = "handler_action_memorize"
    HANDLER_ACTION_RECALL = "handler_action_recall"
    HANDLER_ACTION_FORGET = "handler_action_forget"
    HANDLER_ACTION_TOOL = "handler_action_tool"
    HANDLER_ACTION_DEFER = "handler_action_defer"
    HANDLER_ACTION_REJECT = "handler_action_reject"
    HANDLER_ACTION_PONDER = "handler_action_ponder"
    HANDLER_ACTION_OBSERVE = "handler_action_observe"
    HANDLER_ACTION_TASK_COMPLETE = "handler_action_task_complete"
    SYSTEM_EVENT = "system_event"
    SECURITY_EVENT = "security_event"


class AuditEvent(BaseModel):
    """Schema for audit events."""
    event_type: AuditEventType
    timestamp: str  # ISO8601
    thought_id: Optional[str] = None
    task_id: Optional[str] = None
    handler_name: str
    event_data: Dict[str, Any]
    outcome: str = "success"


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
    agent_template: Optional[str] = None
    round_number: Optional[int] = None
    thought_id: Optional[str] = None
    task_id: Optional[str] = None
