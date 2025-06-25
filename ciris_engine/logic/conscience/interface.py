from __future__ import annotations

from typing import Protocol, runtime_checkable

from ciris_engine.schemas.dma.results import ActionSelectionDMAResult
from ciris_engine.schemas.conscience.core import ConscienceCheckResult

@runtime_checkable
class ConscienceInterface(Protocol):
    """Protocol for all conscience implementations."""

    async def check(
        self,
        action: ActionSelectionDMAResult,
        context: dict,
    ) -> ConscienceCheckResult:
        """Check if action passes conscience."""
        ...
