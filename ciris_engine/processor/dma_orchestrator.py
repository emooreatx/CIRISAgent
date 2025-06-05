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
    EthicalDMAResult,
    CSDMAResult,
    DSDMAResult,
    ActionSelectionResult,
)
from ciris_engine.schemas.processing_schemas_v1 import DMAResults
from ciris_engine.schemas.context_schemas_v1 import ThoughtContext
from ciris_engine.registries.circuit_breaker import CircuitBreaker
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

        # Circuit breakers for each DMA to prevent cascading failures
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
            # Escalate or handle as needed; for now, just raise the first error
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
                        results.ethical_pdma = outcome
                    elif name == "csdma":
                        results.csdma = outcome
                    elif name == "dsdma":
                        results.dsdma = outcome

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
        
        # Populate triaged_inputs correctly
        triaged["original_thought"] = actual_thought
        triaged["processing_context"] = processing_context
        triaged["ethical_pdma_result"] = dma_results.get("ethical_pdma")
        triaged["csdma_result"] = dma_results.get("csdma")
        triaged["dsdma_result"] = dma_results.get("dsdma")
        
        # Extract channel_id from various sources and add to processing_context
        channel_id = None
        
        # From thought context
        if hasattr(actual_thought, 'context') and isinstance(actual_thought.context, dict):
            channel_id = actual_thought.context.get('channel_id')
        
        # From processing_context system_snapshot
        if not channel_id and processing_context.system_snapshot:
            channel_id = processing_context.system_snapshot.channel_id
        
        # From initial task context
        if not channel_id and processing_context.initial_task_context:
            channel_id = getattr(processing_context.initial_task_context, 'channel_id', None)
        
        # Note: ThoughtContext is immutable, channel_id should be set at creation time
        
        # ... rest of the method remains the same
        # Get ponder_count from the actual Thought model
        triaged.setdefault("current_ponder_count", actual_thought.ponder_count)
        
        # Get max_rounds from app_config
        if self.app_config and hasattr(self.app_config, 'workflow'):
            triaged.setdefault("max_rounds", self.app_config.workflow.max_rounds)
        else:
            triaged.setdefault("max_rounds", 5) # Fallback if app_config not available
            logger.warning("DMAOrchestrator: app_config or workflow config not found for max_rounds, using fallback.")

        # Improved agent_profile lookup with fallback logic
        agent_profile_obj = None
        if self.app_config and hasattr(self.app_config, 'agent_profiles'):
            # Try exact match first
            agent_profile_obj = self.app_config.agent_profiles.get(profile_name)  # type: ignore[union-attr]
            if not agent_profile_obj:
                # Try lowercase match
                agent_profile_obj = self.app_config.agent_profiles.get(profile_name.lower())  # type: ignore[union-attr]
            # If still not found and we're not already looking for default, try default
            if not agent_profile_obj and profile_name != "default":
                logger.warning(f"Profile '{profile_name}' not found, falling back to default profile")
                agent_profile_obj = self.app_config.agent_profiles.get("default")  # type: ignore[union-attr]
        if agent_profile_obj:
            logger.debug(f"Using profile '{getattr(agent_profile_obj, 'name', 'unknown')}' for thought {thought_item.thought_id}")
        else:
            logger.warning(f"No profile found for '{profile_name}' or 'default' fallback")
        triaged["agent_profile"] = agent_profile_obj

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
        return result
