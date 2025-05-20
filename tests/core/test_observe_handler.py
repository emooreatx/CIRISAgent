import pytest
from ciris_engine.core.agent_core_schemas import Thought
from ciris_engine.core.action_handlers.observe_handler import handle_observe
from unittest.mock import AsyncMock

class DummyObserver:
    def __init__(self):
        self.observe = AsyncMock()

@pytest.mark.asyncio
async def test_handle_observe():
    t = Thought(thought_id="t", source_task_id="task", created_at="", updated_at="", round_created=0, content="")
    obs = DummyObserver()
    await handle_observe(t, {"x": 1}, obs)
    obs.observe.assert_awaited_with({"x": 1})
    assert t.action_count == 1
    assert t.history[0]["action"] == "observe"
