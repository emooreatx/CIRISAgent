"""Infrastructure service protocols."""

from .authentication import AuthenticationServiceProtocol
from .resource_monitor import ResourceMonitorServiceProtocol
from .database_maintenance import DatabaseMaintenanceServiceProtocol

__all__ = [
    "AuthenticationServiceProtocol",
    "ResourceMonitorServiceProtocol",
    "DatabaseMaintenanceServiceProtocol",
]
