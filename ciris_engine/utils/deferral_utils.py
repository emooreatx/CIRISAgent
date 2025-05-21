from typing import Any, Dict, Optional

from ciris_engine.utils.constants import DEFAULT_WA
from ciris_engine.utils.deferral_package_builder import build_deferral_package
from ciris_engine.core.agent_core_schemas import (
    Thought,
    Task,
    EthicalPDMAResult,
    CSDMAResult,
    DSDMAResult,
    DeferParams,
    ActionSelectionPDMAResult,
)
from ciris_engine.core.foundational_schemas import HandlerActionType


def make_defer_result(
    reason: str,
    trigger: str,
    thought: Optional[Thought],
    parent_task: Optional[Task],
    ethical_pdma: Optional[EthicalPDMAResult],
    csdma: Optional[CSDMAResult],
    dsdma: Optional[DSDMAResult],
    extra: Optional[Dict[str, Any]] = None,
    *,
    context_summary: Optional[str] = None,
) -> ActionSelectionPDMAResult:
    """Create an ActionSelectionPDMAResult representing a DEFER action."""
    package = build_deferral_package(
        thought=thought,
        parent_task=parent_task,
        ethical_pdma_result=ethical_pdma,
        csdma_result=csdma,
        dsdma_result=dsdma,
        trigger_reason=trigger,
        extra=extra,
    )
    params = DeferParams(reason=reason, target_wa_ual=DEFAULT_WA, deferral_package_content=package)
    summary = context_summary or reason
    return ActionSelectionPDMAResult(
        context_summary_for_action_selection=summary,
        action_alignment_check={"Error": reason},
        selected_handler_action=HandlerActionType.DEFER,
        action_parameters=params,
        action_selection_rationale=reason,
        monitoring_for_selected_action={"status": reason},
    )
