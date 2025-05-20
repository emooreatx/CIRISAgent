import pytest
from ciris_engine.core.agent_core_schemas import Thought
from ciris_engine.core.action_handlers.task_complete_handler import handle_task_complete

@pytest.mark.asyncio
async def test_handle_task_complete():
    t = Thought(thought_id="t", source_task_id="task", created_at="", updated_at="", round_created=0, content="")
    await handle_task_complete(t, {})
    assert t.is_terminal
    assert t.action_count == 1
    assert t.history[0]["action"] == "task_complete"
