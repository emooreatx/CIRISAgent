from __future__ import annotations

import logging
from typing import Dict, Any

from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.processing_schemas_v1 import GuardrailResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.action_params_v1 import PonderParams
from ciris_engine.guardrails.registry import GuardrailRegistry
from ciris_engine.registries.circuit_breaker import CircuitBreakerError

logger = logging.getLogger(__name__)


class GuardrailOrchestrator:
    def __init__(self, registry: GuardrailRegistry) -> None:
        self.registry = registry

    async def apply_guardrails(
        self,
        action_result: ActionSelectionResult,
        thought: Thought,
        dma_results_dict: Dict[str, Any],
    ) -> GuardrailResult:
        if action_result.selected_action == HandlerActionType.TASK_COMPLETE:
            return GuardrailResult(
                original_action=action_result,
                final_action=action_result,
                overridden=False,
            )

        context = {"thought": thought, "dma_results": dma_results_dict}

        final_action = action_result
        overridden = False
        override_reason = None
        epistemic_data: Dict[str, Any] = {}

        for entry in self.registry.get_guardrails():
            guardrail = entry.guardrail
            cb = entry.circuit_breaker
            try:
                cb.check_and_raise()
                result = await guardrail.check(final_action, context)
                cb.record_success()
            except CircuitBreakerError as e:
                logger.warning(f"Guardrail {entry.name} unavailable: {e}")
                continue
            except Exception as e:  # noqa: BLE001
                logger.error(f"Guardrail {entry.name} error: {e}", exc_info=True)
                cb.record_failure()
                continue

            epistemic_data[entry.name] = result.epistemic_data
            if not result.passed:
                overridden = True
                override_reason = result.reason
                ponder_params = PonderParams(
                    questions=[result.reason or "Guardrail failed"]
                )
                final_action = ActionSelectionResult(
                    selected_action=HandlerActionType.PONDER,
                    action_parameters=ponder_params.model_dump(mode="json"),
                    rationale=f"Overridden by {entry.name}",
                    confidence=0.3,
                )
                break

        return GuardrailResult(
            original_action=action_result,
            final_action=final_action,
            overridden=overridden,
            override_reason=override_reason,
            epistemic_data=epistemic_data or None,
        )
