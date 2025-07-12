import asyncio
import logging
from typing import Dict, Optional, TYPE_CHECKING, Any

from ciris_engine.logic.dma.pdma import EthicalPDMAEvaluator
from ciris_engine.schemas.processors.dma import (
    DMAMetadata, InitialDMAResults, DMAError, DMAErrors
)
from ciris_engine.logic.dma.csdma import CSDMAEvaluator
from ciris_engine.logic.dma.dsdma_base import BaseDSDMA
from ciris_engine.logic.dma.action_selection_pdma import ActionSelectionPDMAEvaluator
from ciris_engine.logic.dma.dma_executor import (
    run_pdma,
    run_csdma,
    run_dsdma,
    run_action_selection_pdma,
    run_dma_with_retries,
)
from ciris_engine.schemas.dma.results import (
    ActionSelectionDMAResult,
    EthicalDMAResult,
    CSDMAResult,
    DSDMAResult,
)
from ciris_engine.schemas.processors.core import DMAResults
from ciris_engine.schemas.runtime.system_context import ThoughtState
from ciris_engine.logic.registries.circuit_breaker import CircuitBreaker
from ciris_engine.logic.utils.channel_utils import extract_channel_id
from ciris_engine.logic.processors.support.processing_queue import ProcessingQueueItem
from ciris_engine.schemas.runtime.models import Thought

if TYPE_CHECKING:
    from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol

logger = logging.getLogger(__name__)

class DMAOrchestrator:
    def __init__(
        self,
        ethical_pdma_evaluator: EthicalPDMAEvaluator,
        csdma_evaluator: CSDMAEvaluator,
        dsdma: Optional[BaseDSDMA],
        action_selection_pdma_evaluator: ActionSelectionPDMAEvaluator,
        time_service: "TimeServiceProtocol",
        app_config: Optional[Any] = None,
        llm_service: Optional[Any] = None,
        memory_service: Optional[Any] = None,
    ) -> None:
        self.ethical_pdma_evaluator = ethical_pdma_evaluator
        self.csdma_evaluator = csdma_evaluator
        self.dsdma = dsdma
        self.action_selection_pdma_evaluator = action_selection_pdma_evaluator
        self.time_service = time_service
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
        processing_context: Optional[ThoughtState] = None,
        dsdma_context: Optional[DMAMetadata] = None,
    ) -> InitialDMAResults:
        """
        Run EthicalPDMA, CSDMA, and DSDMA in parallel (async). Returns a dict with results or escalates on error.
        """
        logger.info(f"[DEBUG TIMING] run_initial_dmas START for thought {thought_item.thought_id}")
        results = InitialDMAResults()
        errors = DMAErrors()
        tasks = {
            "ethical_pdma": asyncio.create_task(
                run_dma_with_retries(
                    run_pdma,
                    self.ethical_pdma_evaluator,
                    thought_item,
                    processing_context,
                    retry_limit=self.retry_limit,
                    timeout_seconds=self.timeout_seconds,
                    time_service=self.time_service,
                )
            ),
            "csdma": asyncio.create_task(
                run_dma_with_retries(
                    run_csdma,
                    self.csdma_evaluator,
                    thought_item,
                    retry_limit=self.retry_limit,
                    timeout_seconds=self.timeout_seconds,
                    time_service=self.time_service,
                )
            ),
        }
        if self.dsdma:
            tasks["dsdma"] = asyncio.create_task(
                run_dma_with_retries(
                    run_dsdma,
                    self.dsdma,
                    thought_item,
                    dsdma_context or DMAMetadata(),
                    retry_limit=self.retry_limit,
                    timeout_seconds=self.timeout_seconds,
                    time_service=self.time_service,
                )
            )
        else:
            results.dsdma = None

        for name, task in tasks.items():
            try:
                result = await task
                if name == "ethical_pdma":
                    results.ethical_pdma = result
                elif name == "csdma":
                    results.csdma = result
                elif name == "dsdma":
                    results.dsdma = result
            except Exception as e:
                logger.error(f"DMA '{name}' failed: {e}", exc_info=True)
                error = DMAError(
                    dma_name=name,
                    error_message=str(e),
                    error_type=type(e).__name__
                )
                if name == "ethical_pdma":
                    errors.ethical_pdma = error
                elif name == "csdma":
                    errors.csdma = error
                elif name == "dsdma":
                    errors.dsdma = error

        if errors.has_errors():
            raise Exception(f"DMA(s) failed: {errors.get_error_summary()}")
        return results

    async def run_dmas(
        self,
        thought_item: ProcessingQueueItem,
        processing_context: Optional[ThoughtState] = None,
        dsdma_context: Optional[DMAMetadata] = None,
    ) -> "DMAResults":
        """Run all DMAs with circuit breaker protection."""

        from ciris_engine.schemas.processors.core import DMAResults

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
                    time_service=self.time_service,
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
                    time_service=self.time_service,
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
                        dsdma_context or DMAMetadata(),
                        retry_limit=self.retry_limit,
                        timeout_seconds=self.timeout_seconds,
                        time_service=self.time_service,
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
        processing_context: ThoughtState,
        dma_results: InitialDMAResults,
        profile_name: str
    ) -> ActionSelectionDMAResult:
        """Run ActionSelectionPDMAEvaluator sequentially after DMAs."""
        triaged: Dict[str, Any] = {}

        triaged["original_thought"] = actual_thought
        triaged["processing_context"] = processing_context
        triaged["ethical_pdma_result"] = dma_results.ethical_pdma
        triaged["csdma_result"] = dma_results.csdma
        triaged["dsdma_result"] = dma_results.dsdma

        # Check if this is a conscience retry from the context
        if hasattr(processing_context, 'is_conscience_retry') and processing_context.is_conscience_retry:
            triaged["retry_with_guidance"] = True

        channel_id = None

        # Try to get channel_id from various sources
        if processing_context.system_snapshot and processing_context.system_snapshot.channel_context:
            channel_id = extract_channel_id(processing_context.system_snapshot.channel_context)

        if not channel_id and processing_context.initial_task_context:
            channel_context = getattr(processing_context.initial_task_context, 'channel_context', None)
            if channel_context:
                channel_id = extract_channel_id(channel_context)


        triaged.setdefault("current_thought_depth", actual_thought.thought_depth)

        if self.app_config and hasattr(self.app_config, 'workflow'):
            triaged.setdefault("max_rounds", self.app_config.workflow.max_rounds)
        else:
            triaged.setdefault("max_rounds", 5)
            logger.warning("DMAOrchestrator: app_config or workflow config not found for max_rounds, using fallback.")

        # Get identity from persistence tier
        from ciris_engine.logic.persistence.models import get_identity_for_context

        identity_info = get_identity_for_context()
        triaged["agent_identity"] = identity_info.model_dump()  # Convert to dict for backward compatibility

        logger.debug(f"Using identity '{identity_info.agent_name}' for thought {thought_item.thought_id}")

        # Get permitted actions directly from identity
        permitted_actions = identity_info.permitted_actions

        # Identity MUST have permitted actions - no defaults in a mission critical system
        triaged["permitted_actions"] = permitted_actions

        # Pass through conscience feedback if available
        if hasattr(thought_item, 'conscience_feedback') and thought_item.conscience_feedback:
            triaged["conscience_feedback"] = thought_item.conscience_feedback

        try:
            result = await run_dma_with_retries(
                run_action_selection_pdma,
                self.action_selection_pdma_evaluator,
                triaged,
                retry_limit=self.retry_limit,
                timeout_seconds=self.timeout_seconds,
                time_service=self.time_service,
            )
        except Exception as e:
            logger.error(f"ActionSelectionPDMA failed: {e}", exc_info=True)
            raise

        if isinstance(result, ActionSelectionDMAResult):
            return result
        else:
            logger.error(f"Action selection returned unexpected type: {type(result)}")
            raise TypeError(f"Expected ActionSelectionDMAResult, got {type(result)}")
