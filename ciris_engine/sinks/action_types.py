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
    FETCH_GUIDANCE = "request_guidance"
    SEND_DEFERRAL = "submit_deferral"
    MEMORIZE = "memorize"
    RECALL = "recall"
    FORGET = "forget"
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
    
    def __post_init__(self):
        self.type = ActionType.SEND_MESSAGE


@dataclass
class FetchMessagesAction(ActionMessage):
    """Action to fetch messages via communication service"""
    channel_id: str
    limit: int = 10
    
    def __post_init__(self):
        self.type = ActionType.FETCH_MESSAGES


@dataclass
class RequestGuidanceAction(ActionMessage):
    """Action to request guidance from WA service"""
    context: Dict[str, Any]
    
    def __post_init__(self):
        self.type = ActionType.REQUEST_GUIDANCE


@dataclass
class SubmitDeferralAction(ActionMessage):
    """Action to submit deferral to WA service"""
    thought_id: str
    reason: str
    
    def __post_init__(self):
        self.type = ActionType.SUBMIT_DEFERRAL


@dataclass
class MemorizeAction(ActionMessage):
    """Action to memorize data via memory service"""
    key: str
    value: Any
    scope: str
    
    def __post_init__(self):
        self.type = ActionType.MEMORIZE


@dataclass
class RecallAction(ActionMessage):
    """Action to recall data via memory service"""
    key: str
    scope: str
    
    def __post_init__(self):
        self.type = ActionType.RECALL


@dataclass
class ForgetAction(ActionMessage):
    """Action to forget data via memory service"""
    key: str
    scope: str
    
    def __post_init__(self):
        self.type = ActionType.FORGET


# Alias for backward compatibility
DeferralMessage = SubmitDeferralAction
