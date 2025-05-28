"""
ThoughtProcessor: Core logic for processing a single thought in the CIRISAgent pipeline.
Coordinates DMA orchestration, context building, guardrails, and pondering.
"""
import logging
from typing import Optional, Dict, Any

from ciris_engine.schemas.config_schemas_v1 import AppConfig
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.schemas.agent_core_schemas_v1 import ActionSelectionResult, Thought
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, HandlerActionType # Added imports

logger = logging.getLogger(__name__)

class ThoughtProcessor:
    def __init__(
        self,
        dma_orchestrator,
        context_builder,
        guardrail_orchestrator,
        ponder_manager,
        app_config: AppConfig
    ):
        self.dma_orchestrator = dma_orchestrator
        self.context_builder = context_builder
        self.guardrail_orchestrator = guardrail_orchestrator
        self.ponder_manager = ponder_manager
        self.app_config = app_config

    async def process_thought(
        self,
        thought_item: ProcessingQueueItem,
        platform_context: Optional[Dict[str, Any]] = None,
        benchmark_mode: bool = False
    ) -> Optional[ActionSelectionResult]:
        """Main processing pipeline - coordinates the components."""
        # 1. Fetch the full Thought object
        thought = await self._fetch_thought(thought_item.thought_id)
        if not thought:
            logger.error(f"Thought {thought_item.thought_id} not found.")
            return None

        # 2. Build context
        context = await self.context_builder.build_thought_context(thought)

        # 3. Run DMAs
        # profile_name is not an accepted argument by run_initial_dmas.
        # If profile specific DMA behavior is needed, it might be part of thought_item's context
        # or run_initial_dmas and its sub-runners would need to be updated.
        # For now, removing profile_name to fix TypeError.
        # The dsdma_context argument is optional and defaults to None if not provided.
        dma_results = await self.dma_orchestrator.run_initial_dmas(
            thought_item=thought_item
        )

        # 4. Check for failures/escalations
        if self._has_critical_failure(dma_results):
            return self._create_deferral_result(dma_results, thought)

        # 5. Run action selection
        profile_name = self._get_profile_name(thought)
        action_result = await self.dma_orchestrator.run_action_selection(
            thought_item=thought_item,
            actual_thought=thought,
            processing_context=context, # This is the ThoughtContext
            dma_results=dma_results,
            profile_name=profile_name
        )

        # 6. Apply guardrails
        guardrail_result = await self.guardrail_orchestrator.apply_guardrails(
            action_result, thought, dma_results
        )

        # 7. Handle special cases (PONDER, DEFER overrides)
        final_result = await self._handle_special_cases(
            guardrail_result, thought, context
        )

        # 8. Update persistence
        await self._update_thought_status(thought, final_result)

        return final_result

    async def _fetch_thought(self, thought_id: str) -> Optional[Thought]:
        # Import here to avoid circular import
        from ciris_engine import persistence
        return persistence.get_thought_by_id(thought_id)

    def _get_profile_name(self, thought: Thought) -> str:
        # Example: extract from thought context or app_config
        return getattr(thought, 'profile_name', self.app_config.default_profile)

    def _get_permitted_actions(self, thought: Thought) -> Any:
        # Example: extract permitted actions from context or config
        return getattr(thought, 'permitted_actions', None)

    def _has_critical_failure(self, dma_results: Any) -> bool:
        # Placeholder: implement logic to detect critical DMA failures
        return getattr(dma_results, 'critical_failure', False)

    def _create_deferral_result(self, dma_results: Dict[str, Any], thought: Thought) -> ActionSelectionResult:
        from ciris_engine.schemas.action_params_v1 import DeferParams
        from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
        from ciris_engine.utils.constants import DEFAULT_WA

        defer_reason = "Critical DMA failure or guardrail override."
        # Ensure dma_results are serializable if they contain Pydantic models
        serializable_dma_results = {}
        for k, v in dma_results.items():
            if hasattr(v, 'model_dump'):
                serializable_dma_results[k] = v.model_dump(mode='json')
            else:
                serializable_dma_results[k] = v

        defer_params = DeferParams(
            reason=defer_reason,
            target_wa_ual=DEFAULT_WA, # Or a more specific UAL if available
            context={"original_thought_id": thought.thought_id, "dma_results_summary": serializable_dma_results}
        )
        
        return ActionSelectionResult(
            selected_action=HandlerActionType.DEFER,
            action_parameters=defer_params.model_dump(mode='json'), # Pass as dict
            rationale=defer_reason
            # Confidence and raw_llm_response can be None/omitted for system-generated deferrals
        )

    async def _handle_special_cases(self, result, thought, context):
        # HandlerActionType is now imported at the top level
        # Example: handle PONDER, DEFER, or other overrides
        # Support GuardrailResult as well as ActionSelectionResult
        selected_action = None
        if hasattr(result, 'selected_action'):
            selected_action = result.selected_action
        elif hasattr(result, 'final_action') and hasattr(result.final_action, 'selected_action'):
            selected_action = result.final_action.selected_action
        if selected_action == HandlerActionType.PONDER:
            await self.ponder_manager.ponder(thought, context)
        return result

    async def _update_thought_status(self, thought, result):
        from ciris_engine import persistence
        # Update the thought status in persistence
        # Support GuardrailResult as well as ActionSelectionResult
        selected_action = None
        action_parameters = None
        rationale = None
        if hasattr(result, 'selected_action'):
            selected_action = result.selected_action
            action_parameters = getattr(result, 'action_parameters', None)
            rationale = getattr(result, 'rationale', None)
        elif hasattr(result, 'final_action') and hasattr(result.final_action, 'selected_action'):
            selected_action = result.final_action.selected_action
            action_parameters = getattr(result.final_action, 'action_parameters', None)
            rationale = getattr(result.final_action, 'rationale', None)
        new_status_val = ThoughtStatus.COMPLETED # Default, will be overridden by specific actions
        if selected_action == HandlerActionType.DEFER:
            new_status_val = ThoughtStatus.DEFERRED
        elif selected_action == HandlerActionType.PONDER:
            new_status_val = ThoughtStatus.PENDING # Ponder implies it goes back to pending for re-evaluation
        elif selected_action == HandlerActionType.REJECT:
            new_status_val = ThoughtStatus.FAILED # Reject implies failure of this thought path
        # Other actions might imply ThoughtStatus.COMPLETED if they are terminal for the thought.
        final_action_details = {
            "action_type": selected_action.value if selected_action else None,
            "parameters": action_parameters,
            "rationale": rationale
        }
        persistence.update_thought_status(
            thought_id=thought.thought_id,
            status=new_status_val, # Pass ThoughtStatus enum member
            final_action=final_action_details
        )
