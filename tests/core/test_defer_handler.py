import pytest
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import DeferParams
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus
from ciris_engine.core.action_handlers.defer_handler import DeferHandler
from ciris_engine.core.action_handlers.base_handler import ActionHandlerDependencies
from ciris_engine.core import persistence

@pytest.mark.asyncio
async def test_handle_defer(monkeypatch):
    t = Thought(thought_id="t", source_task_id="task", created_at="", updated_at="", round_number=0, content="")
    class DummyDeferral:
        def __init__(self):
            self.called = []
        async def send_deferral(self, *a, **k):
            self.called.append((a, k))
    dummy = DummyDeferral()
    handler = DeferHandler(ActionHandlerDependencies(action_sink=None, deferral_sink=dummy))
    called = {}
    def record_status(**kwargs):
        called.update(kwargs)
    monkeypatch.setattr(persistence, "update_thought_status", record_status)
    result = ActionSelectionResult(
        selected_action=HandlerActionType.DEFER,
        action_parameters=DeferParams(reason="r"),
        rationale="r",
    )
    await handler.handle(result, t, {"channel_id": "1"})
    assert called.get("new_status") == ThoughtStatus.DEFERRED
    assert dummy.called
