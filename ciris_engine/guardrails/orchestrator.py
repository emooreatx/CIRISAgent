from ciris_engine.guardrails import EthicalGuardrails
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.processing_schemas_v1 import DMAResults, GuardrailResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.action_params_v1 import DeferParams, SpeakParams
from ciris_engine.utils import DEFAULT_WA
from ciris_engine.utils.deferral_package_builder import build_deferral_package
from ciris_engine.processor.thought_escalation import escalate_due_to_guardrail
from pydantic import BaseModel
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class GuardrailOrchestrator:
    def __init__(self, ethical_guardrails: EthicalGuardrails):
        self.ethical_guardrails = ethical_guardrails
        
    async def apply_guardrails(
        self,
        action_result: ActionSelectionResult,
        thought: Thought,
        dma_results_dict: Dict[str, Any] # Changed type hint, was DMAResults
    ) -> GuardrailResult:
        """Apply guardrails and handle overrides."""
        # Parse the incoming dict into DMAResults model
        try:
            dma_results = DMAResults(**dma_results_dict)
        except Exception as e:
            logger.error(f"Failed to parse dma_results_dict into DMAResults model: {e}. dma_results_dict: {dma_results_dict}", exc_info=True)
            # Create a default/empty DMAResults if parsing fails to avoid further NoneType errors,
            # though this indicates a problem upstream or with the data.
            dma_results = DMAResults() # Contains Optional fields, so this is valid

        passes_guardrail, reason, epistemic_data = await self.ethical_guardrails.check_action_output_safety(action_result)
        override_action_result = None
        if not passes_guardrail:
            logger.warning(f"Guardrail failed for thought ID {thought.thought_id}: {reason}. Overriding action to DEFER.")
            original_params_as_dict = {}
            if isinstance(action_result.action_parameters, BaseModel):
                original_params_as_dict = action_result.action_parameters.model_dump()
            elif isinstance(action_result.action_parameters, dict):
                original_params_as_dict = action_result.action_parameters
            candidate_response_content = "N/A (Guardrail Deferral)"
            if isinstance(action_result.action_parameters, SpeakParams):
                candidate_response_content = action_result.action_parameters.content
            elif isinstance(original_params_as_dict, dict):
                candidate_response_content = original_params_as_dict.get("content", candidate_response_content)
            parent_task_obj = None
            try:
                from ciris_engine import persistence
                parent_task_obj = persistence.get_task_by_id(thought.source_task_id)
            except Exception:
                pass
            deferral_package_for_guardrail = build_deferral_package(
                thought=thought,
                parent_task=parent_task_obj,
                ethical_pdma_result=dma_results.ethical_pdma,
                csdma_result=dma_results.csdma,
                dsdma_result=dma_results.dsdma,
                trigger_reason="GUARDRAIL_FAILURE",
                extra={
                    "original_proposed_action": action_result.selected_action.value, # Corrected field name
                    "original_action_parameters": original_params_as_dict,
                    "guardrail_failure_reason": reason,
                    "epistemic_data": epistemic_data,
                    "metrics": {"guardrail_triggered": True}
                }
            )
            guardrail_defer_params = DeferParams(
                reason=f"Guardrail failure: {reason}",
                target_wa_ual=DEFAULT_WA,
                context=deferral_package_for_guardrail
            )
            escalate_due_to_guardrail(
                thought,
                reason=(
                    f"Guardrail violation detected: {reason}. DMA: ActionSelectionPDMA, "
                    f"Task: {thought.source_task_id}. "
                    f"Last action: {thought.history[-1]['action']}" if getattr(thought, 'history', None) else "Last action: None"
                ),
            )
            override_action_result = ActionSelectionResult(
                # Fields like context_summary_for_action_selection, action_alignment_check etc. are not in ActionSelectionResult schema.
                # The ActionSelectionResult for DEFER should be minimal.
                selected_action=HandlerActionType.DEFER, # Corrected field name
                action_parameters=guardrail_defer_params.model_dump(mode='json'), # Ensure it's a dict
                rationale=f"Original action '{action_result.selected_action.value}' overridden by guardrail. Reason: {reason}", # Corrected field name
                # confidence and raw_llm_response can be omitted or set to None for system-generated overrides
                raw_llm_response=action_result.raw_llm_response # Keep original raw response if relevant
            )
        final_action = override_action_result if override_action_result else action_result

        return GuardrailResult(
            original_action=action_result,
            final_action=final_action,
            overridden=not passes_guardrail,
            override_reason=reason if not passes_guardrail else None,
            epistemic_data=epistemic_data,
        )
