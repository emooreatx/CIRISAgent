import pytest
from ciris_engine.core.agent_core_schemas import (
    Thought,
    ActionSelectionPDMAResult,
    DeferParams,
)
from ciris_engine.core.foundational_schemas import HandlerActionType, ThoughtStatus
from ciris_engine.core.action_handlers.defer_handler import DeferHandler
from ciris_engine.core.action_handlers.base_handler import ActionHandlerDependencies
from ciris_engine.core import persistence

@pytest.mark.asyncio
async def test_handle_defer(monkeypatch):
    t = Thought(thought_id="t", source_task_id="task", created_at="", updated_at="", round_created=0, content="")
    handler = DeferHandler(ActionHandlerDependencies(action_sink=None))
    called = {}
    def record_status(**kwargs):
        called.update(kwargs)
    monkeypatch.setattr(persistence, "update_thought_status", record_status)
    result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="c",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.DEFER,
        action_parameters=DeferParams(reason="r", target_wa_ual="wa", deferral_package_content={}),
        action_selection_rationale="r",
        monitoring_for_selected_action="m",
    )
    await handler.handle(result, t, {"channel_id": "1"})
    assert called.get("new_status") == ThoughtStatus.DEFERRED
