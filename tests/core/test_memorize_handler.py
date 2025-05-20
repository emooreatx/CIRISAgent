import pytest
from ciris_engine.core.agent_core_schemas import Thought
from ciris_engine.core.action_handlers.memorize_handler import handle_memorize
from unittest.mock import AsyncMock

class DummyMemory:
    def __init__(self):
        self.memorize = AsyncMock()

@pytest.mark.asyncio
async def test_handle_memorize():
    t = Thought(thought_id="t", source_task_id="task", created_at="", updated_at="", round_created=0, content="")
    mem = DummyMemory()
    params = {"user_nick": "bob", "channel": "c", "metadata": {"a": 1}}
    await handle_memorize(t, params, mem)
    mem.memorize.assert_awaited_with("bob", "c", {"a": 1})
    assert t.action_count == 1
    assert t.history[0]["action"] == "memorize"
