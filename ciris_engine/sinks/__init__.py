"""
Multi-service sink implementations that leverage the service registry
for automatic fallback and reliability.
"""

from .multi_service_sink import MultiServiceActionSink
from ciris_engine.schemas.service_actions_v1 import (
    ActionMessage,
    ActionType,
    SendMessageAction,
    FetchMessagesAction,
    FetchGuidanceAction,
    SendDeferralAction,
    MemorizeAction,
    RecallAction,
    ForgetAction,
    SendToolAction,
    FetchToolAction,
)

__all__ = [
    "MultiServiceActionSink",
    "ActionMessage",
    "ActionType",
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
