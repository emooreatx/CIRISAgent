"""AuditService protocol for immutable event logging."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Protocol

from pydantic import BaseModel, Field

from ..types import Outcome, GuardrailHit, Stakeholder


class AuditRecord(BaseModel):
    id: str
    recorded_at: datetime
    direction: str
    stakeholder: Stakeholder
    channel_id: str
    action: str
    outcome: Outcome
    guardrail_hits: list[GuardrailHit] = []
    thought_id: str | None = None
    dma_trace_id: str | None = None
    payload_summary: Dict[str, Any] = Field(default_factory=dict)


class AuditService(Protocol):
    async def record(self, entry: AuditRecord) -> None:
        ...

    async def query(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        stakeholder_id: str | None = None,
        outcome: Outcome | None = None,
        guardrail_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditRecord]:
        ...

