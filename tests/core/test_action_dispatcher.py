import pytest
from unittest.mock import AsyncMock

from ciris_engine.core.action_dispatcher import ActionDispatcher
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, ActionSelectionPDMAResult

class DummyHandler:
    def __init__(self):
        self.handle = AsyncMock()

@pytest.mark.asyncio
async def test_dispatch_invokes_correct_handler():
    t = Thought(
        thought_id="t",
        source_task_id="task",
        created_at="",
        updated_at="",
        round_number=0,
        content="",
    )
    handler = DummyHandler()
    dispatcher = ActionDispatcher({HandlerActionType.SPEAK: handler})
    result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="c",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.SPEAK,
        action_parameters={"content": "hi"},
        action_selection_rationale="r",
        monitoring_for_selected_action="m",
    )
    await dispatcher.dispatch(result, t, {})
    handler.handle.assert_awaited_once_with(result, t, {})

@pytest.mark.asyncio
async def test_action_dispatcher_wrapper():
    handler = DummyHandler()
    dispatcher = ActionDispatcher({HandlerActionType.SPEAK: handler})
    t = Thought(
        thought_id="t",
        source_task_id="task",
        created_at="",
        updated_at="",
        round_number=0,
        content="",
    )
    result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="c",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.SPEAK,
        action_parameters={"content": "hi"},
        action_selection_rationale="r",
        monitoring_for_selected_action="m",
    )
    await dispatcher.dispatch(result, t, {})
    handler.handle.assert_awaited_once_with(result, t, {})
