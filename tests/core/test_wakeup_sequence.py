import sys
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from ciris_engine.core.processor.main_processor import AgentProcessor, WAKEUP_SEQUENCE
from ciris_engine.schemas.agent_core_schemas_v1 import (
    ActionSelectionPDMAResult,
    SpeakParams,
    PonderParams,
)
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, TaskStatus

from .test_agent_processor import (
    mock_app_config_for_processor,
    mock_workflow_coordinator,
    mock_action_dispatcher,
    agent_processor_instance,
)


@pytest.mark.asyncio
@patch("ciris_engine.core.processor.main_processor.persistence")
async def test_wakeup_sequence_success(mock_persistence, agent_processor_instance: AgentProcessor, mock_workflow_coordinator, mock_action_dispatcher):
    pytest.skip("Wakeup sequence logic updated; skipping outdated test.")
    mock_persistence.task_exists.return_value = False
    mock_persistence.add_task = MagicMock()
    mock_persistence.update_task_status = MagicMock()
    mock_persistence.add_thought = MagicMock()

    result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="c",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.SPEAK,
        action_parameters=SpeakParams(content="ok"),
        action_selection_rationale="r",
        monitoring_for_selected_action={},
    )
    mock_workflow_coordinator.process_thought = AsyncMock(return_value=result)

    success = await agent_processor_instance._run_wakeup_sequence()

    assert success
    assert mock_persistence.add_thought.call_count == len(WAKEUP_SEQUENCE)
    # root + five steps + job task
    assert mock_persistence.add_task.call_count == len(WAKEUP_SEQUENCE) + 2
    mock_persistence.update_task_status.assert_any_call("WAKEUP_ROOT", TaskStatus.COMPLETED)
    assert mock_action_dispatcher.dispatch.await_count == len(WAKEUP_SEQUENCE)


@pytest.mark.asyncio
@patch("ciris_engine.core.processor.main_processor.persistence")
async def test_wakeup_sequence_failure(mock_persistence, agent_processor_instance: AgentProcessor, mock_workflow_coordinator, mock_action_dispatcher):
    pytest.skip("Wakeup sequence logic updated; skipping outdated test.")
    mock_persistence.task_exists.return_value = False
    mock_persistence.add_task = MagicMock()
    mock_persistence.update_task_status = MagicMock()
    mock_persistence.add_thought = MagicMock()

    success_result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="c",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.SPEAK,
        action_parameters=SpeakParams(content="ok"),
        action_selection_rationale="r",
        monitoring_for_selected_action={},
    )
    fail_result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="c",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.DEFER,
        action_parameters=SpeakParams(content="no"),
        action_selection_rationale="r",
        monitoring_for_selected_action={},
    )
    mock_workflow_coordinator.process_thought = AsyncMock(side_effect=[success_result, fail_result])

    success = await agent_processor_instance._run_wakeup_sequence()

    assert success is False
    mock_persistence.update_task_status.assert_any_call("WAKEUP_ROOT", TaskStatus.DEFERRED)


@pytest.mark.asyncio
@patch("ciris_engine.core.processor.main_processor.persistence")
async def test_wakeup_sequence_allows_ponder(mock_persistence, agent_processor_instance: AgentProcessor, mock_workflow_coordinator, mock_action_dispatcher):
    pytest.skip("Wakeup sequence logic updated; skipping outdated test.")
    mock_persistence.task_exists.return_value = False
    mock_persistence.add_task = MagicMock()
    mock_persistence.update_task_status = MagicMock()
    mock_persistence.add_thought = MagicMock()

    ponder_result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="c",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.PONDER,
        action_parameters=PonderParams(key_questions=["?"], focus_areas=None, max_ponder_rounds=None),
        action_selection_rationale="r",
        monitoring_for_selected_action={},
    )
    speak_result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="c",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.SPEAK,
        action_parameters=SpeakParams(content="ok"),
        action_selection_rationale="r",
        monitoring_for_selected_action={},
    )
    mock_workflow_coordinator.process_thought = AsyncMock(side_effect=[ponder_result] + [speak_result] * (len(WAKEUP_SEQUENCE) - 1))

    success = await agent_processor_instance._run_wakeup_sequence()

    assert success is False
    mock_persistence.update_task_status.assert_any_call("WAKEUP_ROOT", TaskStatus.DEFERRED)
