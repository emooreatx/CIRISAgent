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

    async def run_action_selection(self, thought_item: ProcessingQueueItem, dma_results: Dict[str, Any], triaged_inputs: Optional[Dict[str, Any]] = None) -> ActionSelectionResult:
        """
        Run ActionSelectionPDMAEvaluator sequentially after DMAs. Returns ActionSelectionResult.
        """
        # Build triaged_inputs for action selection
        triaged = triaged_inputs or {}
        triaged["original_thought"] = getattr(thought_item, "thought", thought_item)
        triaged["ethical_pdma_result"] = dma_results.get("ethical_pdma")
        triaged["csdma_result"] = dma_results.get("csdma")
        triaged["dsdma_result"] = dma_results.get("dsdma")
        triaged.setdefault("current_ponder_count", getattr(thought_item, "ponder_count", 0))
        triaged.setdefault("max_ponder_rounds", getattr(thought_item, "max_ponder_rounds", 1))
        triaged.setdefault("agent_profile", getattr(thought_item, "agent_profile", None))
        try:
            result = await run_action_selection_pdma(self.action_selection_pdma_evaluator, triaged)
        except Exception as e:
            logger.error(f"ActionSelectionPDMA failed: {e}", exc_info=True)
            raise
        return result
