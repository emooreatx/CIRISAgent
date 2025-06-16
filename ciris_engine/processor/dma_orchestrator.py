import asyncio
import logging
from typing import Any, Dict, Optional

from ciris_engine.dma.pdma import EthicalPDMAEvaluator
from ciris_engine.dma.csdma import CSDMAEvaluator
from ciris_engine.dma.dsdma_base import BaseDSDMA
from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAEvaluator
from ciris_engine.dma.dma_executor import (
    run_pdma,
    run_csdma,
    run_dsdma,
    run_action_selection_pdma,
    run_dma_with_retries,
)
from ciris_engine.schemas.dma_results_v1 import (
    ActionSelectionResult,
    EthicalDMAResult,
    CSDMAResult,
    DSDMAResult,
)
from ciris_engine.schemas.processing_schemas_v1 import DMAResults
from ciris_engine.schemas.context_schemas_v1 import ThoughtContext
from ciris_engine.registries.circuit_breaker import CircuitBreaker
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.schemas.agent_core_schemas_v1 import Thought

logger = logging.getLogger(__name__)

class DMAOrchestrator:
    def __init__(
        self,
        ethical_pdma_evaluator: EthicalPDMAEvaluator,
        csdma_evaluator: CSDMAEvaluator,
        dsdma: Optional[BaseDSDMA],
        action_selection_pdma_evaluator: ActionSelectionPDMAEvaluator,
        app_config: Optional[Any] = None,
        llm_service: Optional[Any] = None,
        memory_service: Optional[Any] = None,
    ) -> None:
        self.ethical_pdma_evaluator = ethical_pdma_evaluator
        self.csdma_evaluator = csdma_evaluator
        self.dsdma = dsdma
        self.action_selection_pdma_evaluator = action_selection_pdma_evaluator
        self.app_config = app_config
        self.llm_service = llm_service
        self.memory_service = memory_service

        self.retry_limit = (
            getattr(app_config.workflow, "DMA_RETRY_LIMIT", 3) if app_config else 3
        )
        self.timeout_seconds = (
            getattr(app_config.workflow, "DMA_TIMEOUT_SECONDS", 30.0) if app_config else 30.0
        )

        self._circuit_breakers: Dict[str, CircuitBreaker] = {
            "ethical_pdma": CircuitBreaker("ethical_pdma"),
            "csdma": CircuitBreaker("csdma"),
        }
        if self.dsdma is not None:
            self._circuit_breakers["dsdma"] = CircuitBreaker("dsdma")

    async def run_initial_dmas(
        self,
        thought_item: ProcessingQueueItem,
        processing_context: Optional[ThoughtContext] = None,
        dsdma_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Run EthicalPDMA, CSDMA, and DSDMA in parallel (async). Returns a dict with results or escalates on error.
        """
        results: Dict[str, Any] = {}
        errors: Dict[str, Any] = {}
        tasks = {
            "ethical_pdma": asyncio.create_task(
                run_dma_with_retries(
                    run_pdma,
                    self.ethical_pdma_evaluator,
                    thought_item,
                    processing_context,
                    retry_limit=self.retry_limit,
                    timeout_seconds=self.timeout_seconds,
                )
            ),
            "csdma": asyncio.create_task(
                run_dma_with_retries(
                    run_csdma,
                    self.csdma_evaluator,
                    thought_item,
                    retry_limit=self.retry_limit,
                    timeout_seconds=self.timeout_seconds,
                )
            ),
        }
        if self.dsdma:
            tasks["dsdma"] = asyncio.create_task(
                run_dma_with_retries(
                    run_dsdma,
                    self.dsdma,
                    thought_item,
                    dsdma_context or {},
                    retry_limit=self.retry_limit,
                    timeout_seconds=self.timeout_seconds,
                )
            )
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
            raise Exception(f"DMA(s) failed: {errors}")
        return results

    async def run_dmas(
        self,
        thought_item: ProcessingQueueItem,
        processing_context: Optional[ThoughtContext] = None,
        dsdma_context: Optional[Dict[str, Any]] = None,
    ) -> "DMAResults":
        """Run all DMAs with circuit breaker protection."""

        from ciris_engine.schemas.processing_schemas_v1 import DMAResults

        results = DMAResults()
        tasks: Dict[str, asyncio.Task] = {}

        # Ethical PDMA
        cb = self._circuit_breakers.get("ethical_pdma")
        if cb and cb.is_available():
            tasks["ethical_pdma"] = asyncio.create_task(
                run_dma_with_retries(
                    run_pdma,
                    self.ethical_pdma_evaluator,
                    thought_item,
                    processing_context,
                    retry_limit=self.retry_limit,
                    timeout_seconds=self.timeout_seconds,
                )
            )
        else:
            results.errors.append("ethical_pdma circuit open")

        # CSDMA
        cb = self._circuit_breakers.get("csdma")
        if cb and cb.is_available():
            tasks["csdma"] = asyncio.create_task(
                run_dma_with_retries(
                    run_csdma,
                    self.csdma_evaluator,
                    thought_item,
                    retry_limit=self.retry_limit,
                    timeout_seconds=self.timeout_seconds,
                )
            )
        else:
            results.errors.append("csdma circuit open")

        # DSDMA (optional)
        if self.dsdma:
            cb = self._circuit_breakers.get("dsdma")
            if cb and cb.is_available():
                tasks["dsdma"] = asyncio.create_task(
                    run_dma_with_retries(
                        run_dsdma,
                        self.dsdma,
                        thought_item,
                        dsdma_context or {},
                        retry_limit=self.retry_limit,
                        timeout_seconds=self.timeout_seconds,
                    )
                )
            elif cb:
                results.errors.append("dsdma circuit open")
        else:
            results.dsdma = None

        if tasks:
            task_results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for (name, _), outcome in zip(tasks.items(), task_results):
                cb = self._circuit_breakers.get(name)
                if isinstance(outcome, Exception):
                    logger.error(f"DMA '{name}' failed: {outcome}", exc_info=True)
                    results.errors.append(str(outcome))
                    if cb:
                        cb.record_failure()
                else:
                    if cb:
                        cb.record_success()
                    if name == "ethical_pdma":
                        if isinstance(outcome, EthicalDMAResult):
                            results.ethical_pdma = outcome
                        else:
                            logger.error(f"Unexpected outcome type for ethical_pdma: {type(outcome)}")
                    elif name == "csdma":
                        if isinstance(outcome, CSDMAResult):
                            results.csdma = outcome
                        else:
                            logger.error(f"Unexpected outcome type for csdma: {type(outcome)}")
                    elif name == "dsdma":
                        if isinstance(outcome, DSDMAResult):
                            results.dsdma = outcome
                        else:
                            logger.error(f"Unexpected outcome type for dsdma: {type(outcome)}")

        return results

    async def run_action_selection(
        self,
        thought_item: ProcessingQueueItem,
        actual_thought: Thought,
        processing_context: ThoughtContext,
        dma_results: Dict[str, Any],
        profile_name: str,
        triaged_inputs: Optional[Dict[str, Any]] = None
    ) -> ActionSelectionResult:
        """Run ActionSelectionPDMAEvaluator sequentially after DMAs."""
        triaged = triaged_inputs or {}
        
        triaged["original_thought"] = actual_thought
        triaged["processing_context"] = processing_context
        triaged["ethical_pdma_result"] = dma_results.get("ethical_pdma")
        triaged["csdma_result"] = dma_results.get("csdma")
        triaged["dsdma_result"] = dma_results.get("dsdma")
        
        channel_id = None
        
        if hasattr(actual_thought, 'context') and isinstance(actual_thought.context, dict):
            channel_id = actual_thought.context.get('channel_id')  # type: ignore[unreachable]
        
        if not channel_id and processing_context.system_snapshot:
            channel_id = processing_context.system_snapshot.channel_id
        
        if not channel_id and processing_context.initial_task_context:
            channel_id = getattr(processing_context.initial_task_context, 'channel_id', None)
        
        
        triaged.setdefault("current_ponder_count", actual_thought.ponder_count)
        
        if self.app_config and hasattr(self.app_config, 'workflow'):
            triaged.setdefault("max_rounds", self.app_config.workflow.max_rounds)
        else:
            triaged.setdefault("max_rounds", 5)
            logger.warning("DMAOrchestrator: app_config or workflow config not found for max_rounds, using fallback.")

        # Get identity from persistence tier
        from ciris_engine.persistence.models import get_identity_for_context
        from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
        
        identity_info = get_identity_for_context()
        triaged["agent_identity"] = identity_info
        
        logger.debug(f"Using identity '{identity_info['agent_name']}' for thought {thought_item.thought_id}")
        
        # Extract permitted actions from allowed capabilities
        permitted_actions = []
        for capability in identity_info.get("allowed_capabilities", []):
            # Map capabilities to actions - e.g., "communication" -> SPEAK
            if capability == "communication":
                permitted_actions.extend([HandlerActionType.SPEAK, HandlerActionType.OBSERVE])
            elif capability == "memory":
                permitted_actions.extend([HandlerActionType.MEMORIZE, HandlerActionType.RECALL, HandlerActionType.FORGET])
            elif capability == "task_management":
                permitted_actions.extend([HandlerActionType.TASK_COMPLETE, HandlerActionType.PONDER])
            elif capability == "ethical_reasoning":
                permitted_actions.extend([HandlerActionType.REJECT, HandlerActionType.DEFER])
            elif capability == "tool_use":
                permitted_actions.append(HandlerActionType.TOOL)
        
        # Ensure unique actions
        permitted_actions = list(set(permitted_actions))
        
        if permitted_actions:
            triaged.setdefault("permitted_actions", permitted_actions)
        else:
            from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
            triaged.setdefault("permitted_actions", [
                HandlerActionType.SPEAK, HandlerActionType.PONDER,
                HandlerActionType.REJECT, HandlerActionType.DEFER
            ])
            logger.warning(f"DMAOrchestrator: Agent profile '{profile_name}' or its permitted_actions not found. Using default permitted_actions.")

        try:
            result = await run_dma_with_retries(
                run_action_selection_pdma,
                self.action_selection_pdma_evaluator,
                triaged,
                retry_limit=self.retry_limit,
                timeout_seconds=self.timeout_seconds,
            )
        except Exception as e:
            logger.error(f"ActionSelectionPDMA failed: {e}", exc_info=True)
            raise
        
        if isinstance(result, ActionSelectionResult):
            return result
        else:
            logger.error(f"Action selection returned unexpected type: {type(result)}")
            raise TypeError(f"Expected ActionSelectionResult, got {type(result)}")
