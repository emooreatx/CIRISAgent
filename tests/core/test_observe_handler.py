import pytest
from unittest.mock import AsyncMock
from types import SimpleNamespace

from ciris_engine.schemas.agent_core_schemas_v1 import (
    Thought,
    ActionSelectionPDMAResult,
    ObserveParams,
)
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.core.action_handlers.observe_handler import ObserveHandler
from ciris_engine.core.action_handlers.base_handler import ActionHandlerDependencies
from ciris_engine.core import persistence

class DummyObserver:
    def __init__(self):
        self.observe = AsyncMock()

@pytest.mark.asyncio
async def test_handle_observe(monkeypatch):
    t = Thought(thought_id="t", source_task_id="task", created_at="", updated_at="", round_created=0, content="")
    obs = DummyObserver()
    deps = ActionHandlerDependencies(io_adapter=SimpleNamespace(client=None))
    handler = ObserveHandler(deps)
    added = []
    monkeypatch.setattr(persistence, "add_thought", lambda th: added.append(th))
    monkeypatch.setattr(persistence, "update_thought_status", lambda **k: None)
    params = ObserveParams(sources=["discord"], perform_active_look=False)
    result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="c",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.OBSERVE,
        action_parameters=params,
        action_selection_rationale="r",
        monitoring_for_selected_action="m",
    )
    await handler.handle(result, t, {"current_round_number": 0})
    assert added and added[0].related_thought_id == t.thought_id
