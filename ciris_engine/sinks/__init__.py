"""
Multi-service sink implementations that leverage the service registry
for automatic fallback and reliability.
"""

from .multi_service_sink import MultiServiceActionSink, MultiServiceDeferralSink
from .action_types import (
    ActionMessage, ActionType, DeferralMessage,
    SendMessageAction, FetchMessagesAction, FetchGuidanceAction, SendDeferralAction,
    MemorizeAction, RecallAction, ForgetAction, SendToolAction, FetchToolAction
)

__all__ = [
    "MultiServiceActionSink",
    "MultiServiceDeferralSink", 
    "ActionMessage",
    "ActionType",
    "DeferralMessage",
    "SendMessageAction",
    "FetchMessagesAction", 
    "FetchGuidanceAction",
    "SendDeferralAction",
    "MemorizeAction",
    "RecallAction",
    "ForgetAction",
    "SendToolAction",
    "FetchToolAction",
]
