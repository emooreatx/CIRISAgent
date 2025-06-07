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
                if cb:
                    cb.check_and_raise()
                result = await guardrail.check(final_action, context)
                if cb:
                    cb.record_success()
            except CircuitBreakerError as e:
                logger.warning(f"Guardrail {entry.name} unavailable: {e}")
                continue
            except Exception as e:  # noqa: BLE001
                logger.error(f"Guardrail {entry.name} error: {e}", exc_info=True)
                if cb:
                    cb.record_failure()
                continue

            epistemic_data[entry.name] = result.epistemic_data
            if not result.passed:
                overridden = True
                override_reason = result.reason
                
                # Include information about the attempted action in ponder questions
                attempted_action_desc = self._describe_attempted_action(final_action)
                questions = [
                    f"I attempted to {attempted_action_desc}",
                    result.reason or "Guardrail failed",
                    "What alternative approach would better align with my principles?"
                ]
                
                ponder_params = PonderParams(
                    questions=questions
                )
                final_action = ActionSelectionResult(
                    selected_action=HandlerActionType.PONDER,
                    action_parameters=ponder_params.model_dump(mode="json"),
                    rationale=f"Overridden by {entry.name}: Need to reconsider {attempted_action_desc}",
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
    
    def _describe_attempted_action(self, action_result: ActionSelectionResult) -> str:
        """Generate a human-readable description of the attempted action."""
        action_type = action_result.selected_action
        params = action_result.typed_parameters
        
        descriptions = {
            HandlerActionType.SPEAK: lambda p: f"speak: '{p.content[:100]}...'" if hasattr(p, 'content') and len(p.content) > 100 else f"speak: '{p.content}'" if hasattr(p, 'content') else "speak",
            HandlerActionType.TOOL: lambda p: f"use tool '{p.tool_name}'" if hasattr(p, 'tool_name') else "use a tool",
            HandlerActionType.OBSERVE: lambda p: f"observe channel '{p.channel_id}'" if hasattr(p, 'channel_id') else "observe",
            HandlerActionType.DEFER: lambda p: f"defer with urgency {p.urgency}: '{p.issue[:50]}...'" if hasattr(p, 'urgency') and hasattr(p, 'issue') else "defer to wisdom authority",
            HandlerActionType.MEMORIZE: lambda p: f"memorize {p.node_type} node" if hasattr(p, 'node_type') else "memorize information",
            HandlerActionType.RECALL: lambda p: f"recall {p.node_type} node '{p.node_id}'" if hasattr(p, 'node_type') and hasattr(p, 'node_id') else "recall information",
            HandlerActionType.FORGET: lambda p: f"forget node '{p.node_id}'" if hasattr(p, 'node_id') else "forget information",
            HandlerActionType.REJECT: lambda p: f"reject: '{p.reason[:50]}...'" if hasattr(p, 'reason') else "reject the request",
            HandlerActionType.PONDER: lambda p: "continue pondering",
        }
        
        description_func = descriptions.get(action_type, lambda p: f"perform {action_type.value}")
        
        try:
            return description_func(params)
        except Exception:
            # Fallback if parameter access fails
            return f"perform {action_type.value} action"
