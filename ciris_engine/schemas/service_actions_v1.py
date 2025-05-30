"""
Action and message types for multi-service sinks.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional
from enum import Enum


class ActionType(Enum):
    """Types of actions that can be processed by sinks"""
    SEND_MESSAGE = "send_message"
    FETCH_MESSAGES = "fetch_messages"
    FETCH_GUIDANCE = "fetch_guidance"
    SEND_DEFERRAL = "send_deferral"
    SEND_TOOL = "send_tool"
    FETCH_TOOL = "fetch_tool"


@dataclass
class ActionMessage:
    """Base action message for service sinks"""
    type: ActionType
    handler_name: str
    metadata: Dict[str, Any]


@dataclass
class SendMessageAction(ActionMessage):
    """Action to send a message via communication service"""
    channel_id: str
    content: str
    
    def __init__(self, handler_name: str, metadata: Dict[str, Any], channel_id: str, content: str):
        super().__init__(ActionType.SEND_MESSAGE, handler_name, metadata)
        self.channel_id = channel_id
        self.content = content


@dataclass
class FetchMessagesAction(ActionMessage):
    """Action to fetch messages via communication service"""
    channel_id: str
    limit: int = 10
    
    def __init__(self, handler_name: str, metadata: Dict[str, Any], channel_id: str, limit: int = 10):
        super().__init__(ActionType.FETCH_MESSAGES, handler_name, metadata)
        self.channel_id = channel_id
        self.limit = limit


@dataclass
class FetchGuidanceAction(ActionMessage):
    """Action to fetch guidance from WA service"""
    context: Dict[str, Any]
    
    def __init__(self, handler_name: str, metadata: Dict[str, Any], context: Dict[str, Any]):
        super().__init__(ActionType.FETCH_GUIDANCE, handler_name, metadata)
        self.context = context


@dataclass
class SendDeferralAction(ActionMessage):
    """Action to send deferral to WA service"""
    thought_id: str
    reason: str
    
    def __init__(self, handler_name: str, metadata: Dict[str, Any], thought_id: str, reason: str):
        super().__init__(ActionType.SEND_DEFERRAL, handler_name, metadata)
        self.thought_id = thought_id
        self.reason = reason


@dataclass
class MemorizeAction(ActionMessage):
    """Action to memorize data via memory service"""
    key: str
    value: Any
    scope: str
    
    def __init__(self, handler_name: str, metadata: Dict[str, Any], key: str, value: Any, scope: str):
        super().__init__(ActionType.MEMORIZE, handler_name, metadata)
        self.key = key
        self.value = value
        self.scope = scope


@dataclass
class RecallAction(ActionMessage):
    """Action to recall data via memory service"""
    key: str
    scope: str
    
    def __init__(self, handler_name: str, metadata: Dict[str, Any], key: str, scope: str):
        super().__init__(ActionType.RECALL, handler_name, metadata)
        self.key = key
        self.scope = scope


@dataclass
class ForgetAction(ActionMessage):
    """Action to forget data via memory service"""
    key: str
    scope: str
    
    def __init__(self, handler_name: str, metadata: Dict[str, Any], key: str, scope: str):
        super().__init__(ActionType.FORGET, handler_name, metadata)
        self.key = key
        self.scope = scope


@dataclass
class SendToolAction(ActionMessage):
    """Action to send tool result via tool service"""
    tool_name: str
    tool_args: Dict[str, Any]
    correlation_id: Optional[str] = None
    
    def __init__(self, handler_name: str, metadata: Dict[str, Any], tool_name: str, tool_args: Dict[str, Any], correlation_id: Optional[str] = None):
        super().__init__(ActionType.SEND_TOOL, handler_name, metadata)
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.correlation_id = correlation_id


@dataclass
class FetchToolAction(ActionMessage):
    """Action to fetch tool via tool service"""
    tool_name: str
    correlation_id: str
    timeout: float = 30.0
    
    def __init__(self, handler_name: str, metadata: Dict[str, Any], tool_name: str, correlation_id: str, timeout: float = 30.0):
        super().__init__(ActionType.FETCH_TOOL, handler_name, metadata)
        self.tool_name = tool_name
        self.correlation_id = correlation_id
        self.timeout = timeout


# Alias for backward compatibility
DeferralMessage = SendDeferralAction
