import logging
import asyncio
from typing import Any, Dict, Optional, Callable, Awaitable, TYPE_CHECKING

from ciris_engine.logic.processors.support.thought_escalation import escalate_dma_failure
from ciris_engine.schemas.runtime.models import Thought
from ciris_engine.logic.processors.support.processing_queue import ProcessingQueueItem
from ciris_engine.schemas.runtime.enums import HandlerActionType
from ciris_engine.schemas.runtime.system_context import ThoughtContext

from .pdma import EthicalPDMAEvaluator
from .csdma import CSDMAEvaluator
from .dsdma_base import BaseDSDMA
from .action_selection_pdma import ActionSelectionPDMAEvaluator
from .exceptions import DMAFailure
from ciris_engine.schemas.dma.results import (
    EthicalDMAResult,
    CSDMAResult,
    DSDMAResult,
    ActionSelectionDMAResult,
)

if TYPE_CHECKING:
    from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol

logger = logging.getLogger(__name__)

DMA_RETRY_LIMIT = 3

async def run_dma_with_retries(
    run_fn: Callable[..., Awaitable[Any]],
    *args: Any,
    retry_limit: int = DMA_RETRY_LIMIT,
    timeout_seconds: float = 30.0,
    time_service: Optional["TimeServiceProtocol"] = None,
    **kwargs: Any,
) -> Any:
    """Run a DMA function with retry logic."""
    attempt = 0
    last_error: Optional[Exception] = None
    while attempt < retry_limit:
        try:
            async with asyncio.timeout(timeout_seconds):
                return await run_fn(*args, **kwargs)
        except TimeoutError as e:
            last_error = e
            attempt += 1
            logger.error(
                "DMA %s timed out after %.1f seconds on attempt %s", run_fn.__name__, timeout_seconds, attempt
            )
        except Exception as e:  # noqa: BLE001
            last_error = e
            attempt += 1
            # Only log full details on first failure
            if attempt == 1:
                logger.warning(
                    "DMA %s attempt %s failed: %s", run_fn.__name__, attempt, str(e).replace('\n', ' ')[:200]
                )
            elif attempt == retry_limit:
                logger.warning(
                    "DMA %s final attempt %s failed (same error repeated %s times)", 
                    run_fn.__name__, attempt, attempt - 1
                )
            
            # Add small delay between retries to reduce log spam
            if attempt < retry_limit:
                await asyncio.sleep(0.1)  # 100ms delay

    thought_arg = next(
        (
            arg
            for arg in args
            if isinstance(arg, (Thought, ProcessingQueueItem))
        ),
        None,
    )

    if thought_arg is not None and last_error is not None and time_service is not None:
        escalate_dma_failure(thought_arg, run_fn.__name__, last_error, retry_limit, time_service)

    raise DMAFailure(f"{run_fn.__name__} failed after {retry_limit} attempts: {last_error}")

async def run_pdma(
    evaluator: EthicalPDMAEvaluator,
    thought: ProcessingQueueItem,
    context: Optional[ThoughtContext] = None,
) -> EthicalDMAResult:
    """Run the Ethical PDMA for the given thought."""
    ctx = context
    if ctx is None:
        context_data = getattr(thought, "context", None)
        if context_data is None:
            context_data = getattr(thought, "initial_context", None)

        if context_data is None:
            raise DMAFailure(
                f"No context available for thought {thought.thought_id}"
            )

        if isinstance(context_data, ThoughtContext):
            ctx = context_data
        elif isinstance(context_data, dict):
            try:
                ctx = ThoughtContext.model_validate(context_data)
            except Exception as e:  # noqa: BLE001
                raise DMAFailure(
                    f"Invalid context for thought {thought.thought_id}: {e}"
                ) from e
        else:
            raise DMAFailure(
                f"Unsupported context type {type(context_data)} for thought {thought.thought_id}"
            )

    return await evaluator.evaluate(thought, context=ctx)

async def run_csdma(
    evaluator: CSDMAEvaluator, thought: ProcessingQueueItem
) -> CSDMAResult:
    """Run the CSDMA for the given thought."""
    return await evaluator.evaluate_thought(thought)

async def run_dsdma(
    dsdma: BaseDSDMA,
    thought: ProcessingQueueItem,
    context: Optional[Dict[str, Any]] = None,
) -> DSDMAResult:
    """Run the domain-specific DMA using profile-driven configuration."""
    # Use evaluate method which handles Dict[str, Any] to DMAInputData conversion
    return await dsdma.evaluate(thought, current_context=context)

async def run_action_selection_pdma(
    evaluator: ActionSelectionPDMAEvaluator, triaged_inputs: Dict[str, Any]
) -> ActionSelectionDMAResult:
    """Select the next handler action using the triaged DMA results."""
    logger.debug(f"run_action_selection_pdma: Starting evaluation for thought {triaged_inputs.get('original_thought', {}).thought_id if triaged_inputs.get('original_thought') else 'UNKNOWN'}")
    
    result = await evaluator.evaluate(input_data=triaged_inputs)
    
    logger.debug(f"run_action_selection_pdma: Evaluation completed. Result type: {type(result)}, Result: {result}")
    if result is None:
        logger.error(f"run_action_selection_pdma: evaluator.evaluate() returned None!")  # type: ignore[unreachable]
    elif hasattr(result, 'selected_action'):
        logger.debug(f"run_action_selection_pdma: Selected action: {result.selected_action}")
        if result.selected_action == HandlerActionType.OBSERVE:
            logger.warning(f"OBSERVE ACTION DEBUG: run_action_selection_pdma returning OBSERVE action successfully")
    
    return result
