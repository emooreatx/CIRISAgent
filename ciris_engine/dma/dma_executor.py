import logging
from typing import Any, Dict, Optional, Callable, Awaitable

from ..core.thought_escalation import escalate_dma_failure
from ..core.agent_core_schemas import Thought
from ..core.agent_processing_queue import ProcessingQueueItem

from .pdma import EthicalPDMAEvaluator
from .csdma import CSDMAEvaluator
from .dsdma_base import BaseDSDMA
from .action_selection_pdma import ActionSelectionPDMAEvaluator
from ..core.agent_processing_queue import ProcessingQueueItem
from ..core.dma_results import (
    EthicalPDMAResult,
    CSDMAResult,
    DSDMAResult,
    ActionSelectionPDMAResult,
)

logger = logging.getLogger(__name__)

DMA_RETRY_LIMIT = 3


async def run_dma_with_retries(
    run_fn: Callable[..., Awaitable[Any]],
    *args: Any,
    retry_limit: int = DMA_RETRY_LIMIT,
    **kwargs: Any,
) -> Any:
    """Run a DMA function with retry logic."""
    attempt = 0
    last_error: Optional[Exception] = None
    while attempt < retry_limit:
        try:
            return await run_fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            last_error = e
            attempt += 1
            logger.warning(
                "DMA %s attempt %s failed: %s", run_fn.__name__, attempt, e
            )

    thought_arg = next(
        (
            arg
            for arg in args
            if isinstance(arg, (Thought, ProcessingQueueItem))
        ),
        None,
    )

    if thought_arg is not None:
        return escalate_dma_failure(
            thought_arg, run_fn.__name__, last_error, retry_limit
        )

    raise last_error if last_error else RuntimeError("DMA failure")


async def run_pdma(
    evaluator: EthicalPDMAEvaluator, thought: ProcessingQueueItem
) -> EthicalPDMAResult:
    """Run the Ethical PDMA for the given thought."""
    return await evaluator.evaluate(thought)


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
    return await dsdma.evaluate_thought(thought, context or {})


async def run_action_selection_pdma(
    evaluator: ActionSelectionPDMAEvaluator, triaged_inputs: Dict[str, Any]
) -> ActionSelectionPDMAResult:
    """Select the next handler action using the triaged DMA results."""
    return await evaluator.evaluate(triaged_inputs=triaged_inputs)
