import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from ciris_engine.ponder.manager import PonderManager
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import PonderParams
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus
import asyncio

@pytest.mark.asyncio
@patch("ciris_engine.ponder.manager.persistence.update_thought_status", return_value=True)
async def test_handle_ponder_action_defer(mock_update):
    mgr = PonderManager(max_ponder_rounds=2)
    thought = MagicMock(ponder_count=2, thought_id="tid")
    params = PonderParams(questions=["Q1"])
    result = await mgr.handle_ponder_action(thought, params)
    mock_update.assert_called_once()
    assert result is None
    args, kwargs = mock_update.call_args
    assert kwargs["status"] == ThoughtStatus.DEFERRED
    assert kwargs["final_action"]["action"] == "DEFER"

@pytest.mark.asyncio
@patch("ciris_engine.ponder.manager.persistence.update_thought_status", return_value=True)
async def test_handle_ponder_action_ponder(mock_update):
    mgr = PonderManager(max_ponder_rounds=3)
    thought = MagicMock(ponder_count=1, thought_id="tid")
    params = PonderParams(questions=["Q1"])
    result = await mgr.handle_ponder_action(thought, params)
    mock_update.assert_called_once()
    args, kwargs = mock_update.call_args
    assert kwargs["status"] == ThoughtStatus.PENDING
    assert kwargs["final_action"]["action"] == "PONDER"
    assert result is None

@pytest.mark.asyncio
@patch("ciris_engine.ponder.manager.persistence.update_thought_status")
async def test_handle_ponder_action_update_fail(mock_update):
    mgr = PonderManager(max_ponder_rounds=3)
    thought = MagicMock(ponder_count=1, thought_id="tid")
    params = PonderParams(questions=["Q1"])
    mock_update.side_effect = [False, True]
    result = await mgr.handle_ponder_action(thought, params)
    assert mock_update.call_count >= 2
    assert result is None

@pytest.mark.asyncio
async def test_should_defer_for_max_ponder():
    mgr = PonderManager(max_ponder_rounds=2)
    thought = MagicMock()
    assert mgr.should_defer_for_max_ponder(thought, 2)
    assert not mgr.should_defer_for_max_ponder(thought, 1)

@pytest.mark.asyncio
@patch("ciris_engine.ponder.manager.PonderManager.handle_ponder_action", new_callable=AsyncMock)
async def test_ponder_default_questions(mock_handle):
    mgr = PonderManager()
    thought = MagicMock(ponder_count=0)
    context = {}
    await mgr.ponder(thought, context)
    mock_handle.assert_awaited()
    args, kwargs = mock_handle.call_args
    assert isinstance(kwargs["ponder_params"], PonderParams)
    assert len(kwargs["ponder_params"].questions) >= 1
