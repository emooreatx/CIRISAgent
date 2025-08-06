"""CIRIS Adapter Development Kit (ADK) service contracts."""

from .services.audit import AuditRecord, AuditService
from .services.comms import CommunicationService
from .services.memory import MemoryEntry, MemoryScope, MemoryService  # type: ignore[attr-defined]
from .services.tool import ToolService
from .services.wa import WiseAuthorityService
from .types import *  # noqa: F401,F403

__all__ = [
    "ToolService",
    "CommunicationService",
    "MemoryService",
    "MemoryScope",
    "MemoryEntry",
    "WiseAuthorityService",
    "AuditService",
    "AuditRecord",
]

__adk_version__ = "0.1.0"
