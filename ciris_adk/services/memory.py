"""MemoryService protocol for agent memory storage."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Dict, Protocol

from pydantic import BaseModel, Field


class MemoryScope(StrEnum):
    LOCAL = "local"
    IDENTITY = "identity"
    ENVIRONMENT = "environment"


class MemoryEntry(BaseModel):
    key: str
    value: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MemoryService(Protocol):
    async def store(self, scope: MemoryScope, entry: MemoryEntry) -> None:
        ...

    async def fetch(self, scope: MemoryScope, key: str) -> MemoryEntry | None:
        ...

    async def query(
        self,
        scope: MemoryScope,
        prefix: str | None = None,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        ...

