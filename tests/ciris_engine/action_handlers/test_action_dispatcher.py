import pytest
from unittest.mock import AsyncMock, MagicMock
from ciris_engine.action_handlers.action_dispatcher import ActionDispatcher
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult

class DummyHandler:
    def __init__(self):
        self.called = False
        self.last_args = None
    async def handle(self, action_selection_result, thought, dispatch_context):
        self.called = True
        self.last_args = (action_selection_result, thought, dispatch_context)

@pytest.mark.asyncio
async def test_dispatcher_uses_post_guardrail_action():
    # Setup
    speak_handler = DummyHandler()
    ponder_handler = DummyHandler()
    handlers = {
        HandlerActionType.SPEAK: speak_handler,
        HandlerActionType.PONDER: ponder_handler,
    }
    dispatcher = ActionDispatcher(handlers)
    thought = MagicMock(spec=Thought)
    thought.thought_id = "t1"
    # Simulate guardrail override: original action was SPEAK, but now PONDER
    action_selection_result = MagicMock(spec=ActionSelectionResult)
    action_selection_result.selected_action = HandlerActionType.PONDER
    dispatch_context = {}
    # Act
    await dispatcher.dispatch(action_selection_result, thought, dispatch_context)
    # Assert
    assert ponder_handler.called, "PONDER handler should be called after guardrail override"
    assert not speak_handler.called, "SPEAK handler should NOT be called after guardrail override"
