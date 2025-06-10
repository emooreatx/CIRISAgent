from __future__ import annotations

from typing import Protocol, Dict, Any, runtime_checkable

from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.guardrails_schemas_v1 import GuardrailCheckResult

@runtime_checkable
class GuardrailInterface(Protocol):
    """Protocol for all guardrail implementations."""

    async def check(
        self,
        action: ActionSelectionResult,
        context: Dict[str, Any],
    ) -> GuardrailCheckResult:
        """Check if action passes guardrail."""
        ...
