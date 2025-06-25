"""Graph service protocols."""

from .memory import MemoryServiceProtocol
from .audit import AuditServiceProtocol
from .telemetry import TelemetryServiceProtocol
from .config import GraphConfigServiceProtocol
from .config import GraphConfigServiceProtocol as ConfigServiceProtocol  # Alias for backward compatibility

__all__ = [
    "MemoryServiceProtocol",
    "AuditServiceProtocol",
    "TelemetryServiceProtocol",
    "GraphConfigServiceProtocol",
    "ConfigServiceProtocol",  # Alias
]