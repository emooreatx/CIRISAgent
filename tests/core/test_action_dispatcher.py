import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ciris_engine.core.action_dispatcher import ActionDispatcher
from ciris_engine.core.agent_core_schemas import ActionSelectionPDMAResult, SpeakParams
from ciris_engine.core.foundational_schemas import HandlerActionType

@pytest.mark.asyncio
@patch('ciris_engine.core.persistence.add_thought')
async def test_enqueue_memory_meta_thought(mock_add_thought):
    dispatcher = ActionDispatcher()
    handler = AsyncMock()
    dispatcher.register_service_handler("discord", handler)

    result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="c",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.SPEAK,
        action_parameters=SpeakParams(content="hi"),
        action_selection_rationale="r",
        monitoring_for_selected_action={}
    )

    mock_add_thought.return_value = None
    await dispatcher.dispatch(result, {"origin_service": "discord", "source_task_id": "t1", "author_name": "a", "channel_id": "c"})

    assert mock_add_thought.called
