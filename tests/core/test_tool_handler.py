import pytest
from ciris_engine.core.agent_core_schemas import Thought
from ciris_engine.core.action_handlers.tool_handler import handle_tool
from unittest.mock import AsyncMock

class DummyTool:
    def __init__(self):
        self.execute_tool = AsyncMock()

@pytest.mark.asyncio
async def test_handle_tool():
    t = Thought(thought_id="t", source_task_id="task", created_at="", updated_at="", round_created=0, content="")
    tool = DummyTool()
    new_thought = await handle_tool(t, {"tool_name": "x", "arguments": {"a": 1}}, tool)
    tool.execute_tool.assert_awaited_with("x", {"a": 1})
    assert new_thought.related_thought_id == t.thought_id
