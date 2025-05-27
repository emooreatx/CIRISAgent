import pytest
from unittest.mock import AsyncMock

from ciris_engine.schemas.agent_core_schemas_v1 import (
    Thought,
    ActionSelectionPDMAResult,
    MemorizeParams,
)
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.action_handlers.memorize_handler import MemorizeHandler
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies
from ciris_engine.memory.ciris_local_graph import MemoryOpStatus
from ciris_engine import persistence

class DummyMemory:
    def __init__(self):
        self.memorize = AsyncMock()

@pytest.mark.asyncio
async def test_handle_memorize(monkeypatch):
    t = Thought(thought_id="t", source_task_id="task", created_at="", updated_at="", round_created=0, content="")
    mem = DummyMemory()
    deps = ActionHandlerDependencies(memory_service=mem)
    handler = MemorizeHandler(deps)
    mem.memorize.return_value = AsyncMock(status=MemoryOpStatus.OK)
    added = []
    monkeypatch.setattr(persistence, "add_thought", lambda th: added.append(th))
    monkeypatch.setattr(persistence, "update_thought_status", lambda **k: None)
    params = MemorizeParams(
        knowledge_unit_description="desc",
        knowledge_data={"nick": "bob"},
        knowledge_type="profile",
        source="discord",
        confidence=0.9,
        channel_metadata={"channel": "c"},
    )
    result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="c",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.MEMORIZE,
        action_parameters=params,
        action_selection_rationale="r",
        monitoring_for_selected_action="m",
    )
    await handler.handle(result, t, {"author_name": "bob", "channel_id": "c"})
    mem.memorize.assert_awaited()
    assert added and added[0].related_thought_id == t.thought_id
