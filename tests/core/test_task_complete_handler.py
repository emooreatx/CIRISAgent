import pytest

from ciris_engine.schemas.agent_core_schemas_v1 import (
    Thought,
    ActionSelectionPDMAResult,
)
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, TaskStatus
from ciris_engine.core.action_handlers.task_complete_handler import TaskCompleteHandler
from ciris_engine.core.action_handlers.base_handler import ActionHandlerDependencies
from ciris_engine.core import persistence

@pytest.mark.asyncio
async def test_handle_task_complete(monkeypatch):
    t = Thought(thought_id="t", source_task_id="task", created_at="", updated_at="", round_created=0, content="")
    called = {}
    def record_task_status(task_id, status):
        called["task_status"] = status
    monkeypatch.setattr(persistence, "update_task_status", record_task_status)
    monkeypatch.setattr(persistence, "update_thought_status", lambda **k: called.update(k))
    handler = TaskCompleteHandler(ActionHandlerDependencies(action_sink=None))
    result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="c",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.TASK_COMPLETE,
        action_parameters={},
        action_selection_rationale="r",
        monitoring_for_selected_action="m",
    )
    await handler.handle(result, t, {"channel_id": "1"})
    assert called["task_status"] == TaskStatus.COMPLETED
