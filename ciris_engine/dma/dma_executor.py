import logging
from typing import Any, Dict, Optional

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
