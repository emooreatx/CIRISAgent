"""CIRIS Adapter Development Kit (ADK) service contracts."""

from .types import *  # noqa: F401,F403
from .services.tool import ToolService
from .services.comms import CommunicationService
from .services.memory import MemoryService, MemoryScope, MemoryEntry  # type: ignore[attr-defined]
from .services.wa import WiseAuthorityService
from .services.audit import AuditService, AuditRecord

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
