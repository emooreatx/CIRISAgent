import logging
from typing import Optional, Dict, Any

from ciris_engine.core.dma.orchestrator import DMAOrchestrator
from ciris_engine.core.context.builder import ContextBuilder
from ciris_engine.core.guardrails.orchestrator import GuardrailOrchestrator
from ciris_engine.core.ponder.manager import PonderManager
from ciris_engine.schemas.config_schemas_v1 import AppConfig
from ciris_engine.core.agent_processing_queue import ProcessingQueueItem
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult

logger = logging.getLogger(__name__)

class ThoughtProcessor:
    def __init__(
        self,
        dma_orchestrator: DMAOrchestrator,
        context_builder: ContextBuilder,
        guardrail_orchestrator: GuardrailOrchestrator,
        ponder_manager: PonderManager,
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
        # 1. Build context
        thought = await self._fetch_thought(thought_item.thought_id)
        context = await self.context_builder.build_thought_context(thought)

        # 2. Run DMAs
        dma_results = await self.dma_orchestrator.run_initial_dmas(
            thought_item,
            profile_name=self._get_profile_name(thought)
        )

        # 3. Check for failures/escalations
        if self._has_critical_failure(dma_results):
            return self._create_deferral_result(dma_results, thought)

        # 4. Run action selection
        action_result = await self.dma_orchestrator.run_action_selection(
            dma_results, thought, self._get_permitted_actions(thought)
        )

        # 5. Apply guardrails
        guardrail_result = await self.guardrail_orchestrator.apply_guardrails(
            action_result, thought, dma_results
        )

        # 6. Handle special cases (PONDER, DEFER overrides)
        final_result = await self._handle_special_cases(
            guardrail_result, thought, context
        )

        # 7. Update persistence
        await self._update_thought_status(thought, final_result)

        return final_result

    async def _fetch_thought(self, thought_id: str) -> Thought:
        # Placeholder for fetching a Thought object from persistence
        from ciris_engine.core import persistence
        return persistence.get_thought_by_id(thought_id)

    def _get_profile_name(self, thought: Thought) -> Optional[str]:
        # Extract profile name from the thought or context
        return getattr(thought, 'profile_name', None)

    def _get_permitted_actions(self, thought: Thought):
        # Determine permitted actions for the thought's profile
        profile_name = self._get_profile_name(thought)
        if profile_name and hasattr(self.app_config, 'agent_profiles'):
            profile = self.app_config.agent_profiles.get(profile_name)
            if profile:
                return profile.permitted_actions
        return []

    def _has_critical_failure(self, dma_results) -> bool:
        # Placeholder: implement logic to check for critical DMA failures
        return False

    def _create_deferral_result(self, dma_results, thought: Thought):
        # Placeholder: implement logic to create a deferral ActionSelectionResult
        return None

    async def _handle_special_cases(self, guardrail_result, thought, context):
        # Placeholder: handle PONDER, DEFER, or other special actions
        return guardrail_result.override_action_result or guardrail_result

    async def _update_thought_status(self, thought: Thought, result: ActionSelectionResult):
        # Placeholder: update persistence with the final result
        from ciris_engine.core import persistence
        persistence.update_thought_status(
            thought_id=thought.thought_id,
            new_status="COMPLETED",
            round_processed=None,
            final_action_result=result.model_dump() if result else None
        )
