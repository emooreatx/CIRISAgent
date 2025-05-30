"""
Multi-service sink implementations that leverage the service registry
for automatic fallback and reliability.
"""

from .multi_service_sink import MultiServiceActionSink, MultiServiceDeferralSink
from .action_types import ActionMessage, DeferralMessage

__all__ = [
    "MultiServiceActionSink",
    "MultiServiceDeferralSink", 
    "ActionMessage",
    "DeferralMessage",
]
