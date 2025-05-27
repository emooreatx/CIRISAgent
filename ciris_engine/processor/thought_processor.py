"""
ThoughtProcessor: Core logic for processing a single thought in the CIRISAgent pipeline.
Coordinates DMA orchestration, context building, guardrails, and pondering.
"""
import logging
from typing import Optional, Dict, Any

from ciris_engine.schemas.config_schemas_v1 import AppConfig
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.schemas.agent_core_schemas_v1 import ActionSelectionResult, Thought

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
        dma_results = await self.dma_orchestrator.run_initial_dmas(
            thought_item, 
            profile_name=self._get_profile_name(thought)
        )

        # 4. Check for failures/escalations
        if self._has_critical_failure(dma_results):
            return self._create_deferral_result(dma_results, thought)

        # 5. Run action selection
        action_result = await self.dma_orchestrator.run_action_selection(
            dma_results, thought, self._get_permitted_actions(thought)
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

    def _create_deferral_result(self, dma_results: Any, thought: Thought) -> ActionSelectionResult:
        # Placeholder: create a deferral ActionSelectionResult
        return ActionSelectionResult(
            thought_id=thought.thought_id,
            selected_handler_action='DEFER',
            details={"reason": "Critical DMA failure", "dma_results": dma_results}
        )

    async def _handle_special_cases(self, result: ActionSelectionResult, thought: Thought, context: Dict[str, Any]) -> ActionSelectionResult:
        # Example: handle PONDER, DEFER, or other overrides
        if result.selected_handler_action == 'PONDER':
            await self.ponder_manager.ponder(thought, context)
        return result

    async def _update_thought_status(self, thought: Thought, result: ActionSelectionResult):
        from ciris_engine import persistence
        # Update the thought status in persistence
        persistence.update_thought_status(
            thought_id=thought.thought_id,
            new_status=result.selected_handler_action,
            final_action=result.details
        )
