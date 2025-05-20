import logging
from typing import Any, Dict, Optional, Callable, Awaitable

from .thought_escalation import escalate_dma_failure
from .agent_core_schemas import Thought
from .agent_processing_queue import ProcessingQueueItem
from .dma_results import (
    EthicalPDMAResult,
    CSDMAResult,
    DSDMAResult,
    ActionSelectionPDMAResult,
)
from .config_schemas import DMA_RETRY_LIMIT

from ..dma.pdma import EthicalPDMAEvaluator
from ..dma.csdma import CSDMAEvaluator
from ..dma.dsdma_base import BaseDSDMA
from ..dma.action_selection_pdma import ActionSelectionPDMAEvaluator

logger = logging.getLogger(__name__)


async def run_dma_with_retries(
    run_fn: Callable[..., Awaitable[Any]],
    *args: Any,
    retry_limit: int = DMA_RETRY_LIMIT,
    **kwargs: Any,
) -> Any:
    """Run a DMA function with simple retry logic."""
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
    evaluator: EthicalPDMAEvaluator,
    thought: ProcessingQueueItem,
    *,
    retry_limit: int = DMA_RETRY_LIMIT,
) -> EthicalPDMAResult:
    """Run the Ethical PDMA for the given thought with retries."""
    return await run_dma_with_retries(evaluator.evaluate, thought, retry_limit=retry_limit)


async def run_csdma(
    evaluator: CSDMAEvaluator,
    thought: ProcessingQueueItem,
    *,
    retry_limit: int = DMA_RETRY_LIMIT,
) -> CSDMAResult:
    """Run the CSDMA for the given thought with retries."""
    return await run_dma_with_retries(
        evaluator.evaluate_thought, thought, retry_limit=retry_limit
    )


async def run_dsdma(
    dsdma: BaseDSDMA,
    thought: ProcessingQueueItem,
    context: Optional[Dict[str, Any]] = None,
    *,
    retry_limit: int = DMA_RETRY_LIMIT,
) -> DSDMAResult:
    """Run the domain-specific DMA with retries."""
    return await run_dma_with_retries(
        dsdma.evaluate_thought, thought, context or {}, retry_limit=retry_limit
    )


async def run_action_selection_pdma(
    evaluator: ActionSelectionPDMAEvaluator,
    triaged_inputs: Dict[str, Any],
    *,
    retry_limit: int = DMA_RETRY_LIMIT,
) -> ActionSelectionPDMAResult:
    """Select the next handler action using the triaged DMA results."""
    return await run_dma_with_retries(
        evaluator.evaluate, triaged_inputs=triaged_inputs, retry_limit=retry_limit
    )
