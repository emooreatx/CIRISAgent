"""Infrastructure service protocols."""

from .authentication import AuthenticationServiceProtocol
from .resource_monitor import ResourceMonitorServiceProtocol

__all__ = [
    "AuthenticationServiceProtocol",
    "ResourceMonitorServiceProtocol",
]
