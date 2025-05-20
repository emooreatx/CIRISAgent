import pytest
from unittest.mock import AsyncMock, patch

from ciris_engine.core.action_dispatcher import ActionDispatcher, dispatch, handler_map
from ciris_engine.core.foundational_schemas import HandlerActionType
from ciris_engine.core.agent_core_schemas import Thought

@pytest.mark.asyncio
async def test_dispatch_invokes_correct_handler():
    t = Thought(thought_id="t", source_task_id="task", created_at="", updated_at="", round_created=0, content="")
    mock_handler = AsyncMock()
    with patch.dict(handler_map, {HandlerActionType.SPEAK: mock_handler}):
        await dispatch(HandlerActionType.SPEAK, t, {"content": "hi"}, {})
        mock_handler.assert_awaited_once()

@pytest.mark.asyncio
async def test_action_dispatcher_wrapper():
    dispatcher = ActionDispatcher()
    mock_handler = AsyncMock()
    with patch.dict(handler_map, {HandlerActionType.SPEAK: mock_handler}):
        await dispatcher.dispatch(HandlerActionType.SPEAK, Thought(thought_id="t", source_task_id="task", created_at="", updated_at="", round_created=0, content=""), {"content": "hi"}, {})
        mock_handler.assert_awaited_once()
