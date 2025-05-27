import asyncio
import logging
from typing import Any, Dict, Optional

from ciris_engine.dma.pdma import EthicalPDMAEvaluator
from ciris_engine.dma.csdma import CSDMAEvaluator
from ciris_engine.dma.dsdma_base import BaseDSDMA
from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAEvaluator
from ciris_engine.dma.dma_executor import run_pdma, run_csdma, run_dsdma, run_action_selection_pdma
from ciris_engine.schemas.dma_results_v1 import EthicalDMAResult, CSDMAResult, DSDMAResult, ActionSelectionResult
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.schemas.agent_core_schemas_v1 import Thought # Added import

logger = logging.getLogger(__name__)

class DMAOrchestrator:
    def __init__(
        self,
        ethical_pdma_evaluator: EthicalPDMAEvaluator,
        csdma_evaluator: CSDMAEvaluator,
        dsdma: Optional[BaseDSDMA],
        action_selection_pdma_evaluator: ActionSelectionPDMAEvaluator,
        app_config: Any = None,
        llm_service: Any = None,
        memory_service: Any = None,
    ):
        self.ethical_pdma_evaluator = ethical_pdma_evaluator
        self.csdma_evaluator = csdma_evaluator
        self.dsdma = dsdma
        self.action_selection_pdma_evaluator = action_selection_pdma_evaluator
        self.app_config = app_config
        self.llm_service = llm_service
        self.memory_service = memory_service

    async def run_initial_dmas(self, thought_item: ProcessingQueueItem, dsdma_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Run EthicalPDMA, CSDMA, and DSDMA in parallel (async). Returns a dict with results or escalates on error.
        """
        results = {}
        errors = {}
        tasks = {
            "ethical_pdma": asyncio.create_task(run_pdma(self.ethical_pdma_evaluator, thought_item)),
            "csdma": asyncio.create_task(run_csdma(self.csdma_evaluator, thought_item)),
        }
        if self.dsdma:
            tasks["dsdma"] = asyncio.create_task(run_dsdma(self.dsdma, thought_item, dsdma_context or {}))
        else:
            results["dsdma"] = None

        for name, task in tasks.items():
            try:
                results[name] = await task
            except Exception as e:
                logger.error(f"DMA '{name}' failed: {e}", exc_info=True)
                errors[name] = e
                results[name] = None

        if errors:
            # Escalate or handle as needed; for now, just raise the first error
            raise Exception(f"DMA(s) failed: {errors}")
        return results

    async def run_action_selection(
        self,
        thought_item: ProcessingQueueItem, # Contains queue-level info like thought_id, initial_context
        actual_thought: Thought,           # The full Thought model instance
        processing_context: Dict[str, Any], # This is the ThoughtContext
        dma_results: Dict[str, Any],
        profile_name: str, # Added to fetch AgentProfile
        triaged_inputs: Optional[Dict[str, Any]] = None
    ) -> ActionSelectionResult:
        """
        Run ActionSelectionPDMAEvaluator sequentially after DMAs. Returns ActionSelectionResult.
        """
        triaged = triaged_inputs or {}
        
        # Populate triaged_inputs correctly
        triaged["original_thought"] = actual_thought # Use the actual Thought model
        triaged["processing_context"] = processing_context # Pass the full ThoughtContext
        triaged["ethical_pdma_result"] = dma_results.get("ethical_pdma")
        triaged["csdma_result"] = dma_results.get("csdma")
        triaged["dsdma_result"] = dma_results.get("dsdma")
        
        # Get ponder_count from the actual Thought model
        triaged.setdefault("current_ponder_count", actual_thought.ponder_count)
        
        # Get max_ponder_rounds from app_config
        if self.app_config and hasattr(self.app_config, 'workflow'):
            triaged.setdefault("max_ponder_rounds", self.app_config.workflow.max_ponder_rounds)
        else:
            triaged.setdefault("max_ponder_rounds", 5) # Fallback if app_config not available
            logger.warning("DMAOrchestrator: app_config or workflow config not found for max_ponder_rounds, using fallback.")

        # Get agent_profile from app_config using profile_name
        agent_profile_obj = None
        if self.app_config and hasattr(self.app_config, 'agent_profiles') and profile_name:
            agent_profile_obj = self.app_config.agent_profiles.get(profile_name)
        triaged.setdefault("agent_profile", agent_profile_obj)
        
        # Get permitted_actions from the agent_profile if available
        if agent_profile_obj and hasattr(agent_profile_obj, 'permitted_actions'):
            triaged.setdefault("permitted_actions", agent_profile_obj.permitted_actions)
        else:
            # Default permitted actions if profile or its actions are not found
            from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType # Local import
            triaged.setdefault("permitted_actions", [
                HandlerActionType.SPEAK, HandlerActionType.PONDER,
                HandlerActionType.REJECT, HandlerActionType.DEFER
            ])
            logger.warning(f"DMAOrchestrator: Agent profile '{profile_name}' or its permitted_actions not found. Using default permitted_actions.")

        try:
            result = await run_action_selection_pdma(self.action_selection_pdma_evaluator, triaged)
        except Exception as e:
            logger.error(f"ActionSelectionPDMA failed: {e}", exc_info=True)
            # The error is re-raised here, so the caller (ThoughtProcessor) will handle it.
            # No need to create a fallback ActionSelectionResult here as ThoughtProcessor does that.
            raise
        return result
