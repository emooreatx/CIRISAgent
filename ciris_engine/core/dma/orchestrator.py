from typing import Dict, Optional, List
import asyncio
from ciris_engine.schemas.dma_results_v1 import EthicalDMAResult, CSDMAResult, DSDMAResult, ActionSelectionResult
from ciris_engine.schemas.processing_schemas_v1 import DMAResults
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.core.agent_processing_queue import ProcessingQueueItem

class DMAOrchestrator:
    def __init__(
        self,
        ethical_pdma,
        csdma,
        action_selection_pdma,
        dsdma_registry: Dict[str, object]
    ):
        self.ethical_pdma = ethical_pdma
        self.csdma = csdma
        self.action_selection_pdma = action_selection_pdma
        self.dsdma_registry = dsdma_registry
        
    async def run_initial_dmas(
        self,
        thought: ProcessingQueueItem,
        profile_name: Optional[str] = None,
        retry_limit: int = 3
    ) -> DMAResults:
        """Run PDMA, CSDMA, and DSDMA concurrently."""
        # Fetch the full Thought object using the thought_id from ProcessingQueueItem
        from ciris_engine.core import persistence
        from ciris_engine.schemas.dma_results_v1 import EthicalDMAResult, CSDMAResult, DSDMAResult
        thought_object = persistence.get_thought_by_id(thought.thought_id)
        initial_dma_tasks = []
        initial_dma_tasks.append(self.ethical_pdma.evaluate(thought_object, retry_limit=retry_limit))
        initial_dma_tasks.append(self.csdma.evaluate(thought_object, retry_limit=retry_limit))
        dsdma_result = None
        if self.dsdma_registry and profile_name:
            dsdma = self.dsdma_registry.get(profile_name)
            if dsdma:
                initial_dma_tasks.append(dsdma.evaluate(thought_object, retry_limit=retry_limit))
        results = await asyncio.gather(*initial_dma_tasks, return_exceptions=True)
        ethical_pdma_result = results[0] if isinstance(results[0], EthicalDMAResult) else None
        csdma_result = results[1] if isinstance(results[1], CSDMAResult) else None
        dsdma_result = results[2] if len(results) > 2 and isinstance(results[2], DSDMAResult) else None
        errors = [str(r) for r in results if isinstance(r, Exception)]
        return DMAResults(
            ethical_pdma=ethical_pdma_result,
            csdma=csdma_result,
            dsdma=dsdma_result,
            errors=errors
        )

    async def run_action_selection(
        self,
        dma_results: DMAResults,
        thought: Thought,
        permitted_actions: List[HandlerActionType],
        benchmark_mode: bool = False
    ) -> ActionSelectionResult:
        """Run the action selection PDMA."""
        triaged_inputs_for_action_selection = {
            "original_thought": thought,
            "ethical_pdma_result": dma_results.ethical_pdma,
            "csdma_result": dma_results.csdma,
            "dsdma_result": dma_results.dsdma,
            "current_ponder_count": getattr(thought, 'ponder_count', 0),
            "max_ponder_rounds": getattr(thought, 'max_ponder_rounds', 3),
            "benchmark_mode": benchmark_mode,
            "permitted_actions": permitted_actions,
            # Optionally add agent_profile if needed
        }
        # You may want to pass agent_profile if available in your context
        return await self.action_selection_pdma.evaluate(triaged_inputs_for_action_selection)
