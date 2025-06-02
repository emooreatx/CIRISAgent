from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel
from .foundational_schemas_v1 import CaseInsensitiveEnum

class MemoryOpStatus(CaseInsensitiveEnum):
    """Status of a memory operation."""
    OK = "ok"
    DEFERRED = "deferred"
    DENIED = "denied"

class MemoryOpAction(str, Enum):
    """Memory operation types."""
    MEMORIZE = "memorize"
    RECALL = "recall"
    FORGET = "forget"

class MemoryOpResult(BaseModel):
    """Result of a memory operation."""
    status: MemoryOpStatus
    reason: Optional[str] = None
    data: Optional[Any] = None

__all__ = [
    "MemoryOpStatus",
    "MemoryOpAction",
    "MemoryOpResult",
]
