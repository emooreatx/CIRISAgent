"""Minimal workflow coordinator.

This coordinator is intentionally small for pre-alpha refactoring work. It
receives a :class:`Thought` and returns the recommended
:class:`HandlerActionType`. Real DMA logic will be integrated later.
"""

from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.guardrails_config_v1 import GuardrailsConfig
from ciris_engine.schemas.dma_results_v1 import EthicalDMAResult
from .pdma import PDMAEvaluator


class Coordinator:
    """Coordinator that selects actions using a PDMA evaluator."""

    def __init__(self, guardrails: GuardrailsConfig | None = None) -> None:
        self.guardrails = guardrails or GuardrailsConfig()
        self.pdma = PDMAEvaluator(self.guardrails)
        self.last_pdma_result: EthicalDMAResult | None = None

    async def process_thought(self, thought: Thought) -> HandlerActionType:
        """Run the PDMA evaluator and return the chosen action."""
        self.last_pdma_result = await self.pdma.evaluate(thought)
        decision = self.last_pdma_result.decision
        if decision == HandlerActionType.SPEAK.value:
            return HandlerActionType.SPEAK
        if decision == HandlerActionType.PONDER.value:
            return HandlerActionType.PONDER
        if decision == HandlerActionType.DEFER.value:
            return HandlerActionType.DEFER
        return HandlerActionType.PONDER
