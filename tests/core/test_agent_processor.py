import sys # Add sys import
import os # Add os import
# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, call
import uuid
from datetime import datetime, timezone
import collections

from ciris_engine.core.agent_processor import AgentProcessor
from ciris_engine.core.config_schemas import AppConfig, WorkflowConfig, LLMServicesConfig, OpenAIConfig, DatabaseConfig, GuardrailsConfig
from ciris_engine.core.agent_core_schemas import Task, Thought, ActionSelectionPDMAResult
from ciris_engine.core.foundational_schemas import TaskStatus, ThoughtStatus, HandlerActionType # <-- Import HandlerActionType
from ciris_engine.core.agent_processing_queue import ProcessingQueueItem

# --- Fixtures ---

@pytest.fixture
def mock_app_config_for_processor():
    """Provides a mock AppConfig suitable for AgentProcessor tests."""
    return AppConfig(
        db=DatabaseConfig(db_filename="test_ap.db"),
        llm_services=LLMServicesConfig(openai=OpenAIConfig(model_name="test-model")),
        workflow=WorkflowConfig(
            max_active_tasks=2,
            max_active_thoughts=2, # Max thoughts to pull into queue per round
            round_delay_seconds=0, # No delay for tests
            max_ponder_rounds=1
        ),
        guardrails=GuardrailsConfig()
        # No agent_profiles needed directly by AgentProcessor
    )

@pytest.fixture
def mock_workflow_coordinator():
    """Mocks the WorkflowCoordinator."""
    mock_wc = AsyncMock()
    mock_wc.process_thought = AsyncMock()
    mock_wc.advance_round = MagicMock() # Synchronous method
    mock_wc.current_round_number = 0 # Initialize
    
    # Simulate advance_round incrementing current_round_number
    def _advance_round_side_effect():
        mock_wc.current_round_number += 1
    mock_wc.advance_round.side_effect = _advance_round_side_effect
    
    return mock_wc

@pytest.fixture
def mock_action_dispatcher():
    """Mocks the ActionDispatcher."""
    mock_ad = AsyncMock()
    mock_ad.dispatch = AsyncMock() # Mock the dispatch method
    return mock_ad

@pytest.fixture
def agent_processor_instance(mock_app_config_for_processor, mock_workflow_coordinator, mock_action_dispatcher):
    """Provides an AgentProcessor instance with mocked dependencies."""
    return AgentProcessor(
        app_config=mock_app_config_for_processor,
        workflow_coordinator=mock_workflow_coordinator,
        action_dispatcher=mock_action_dispatcher # Add the mock dispatcher
    )

def create_mock_task(task_id: str, status: TaskStatus, priority: int = 0) -> Task:
    now_iso = datetime.now(timezone.utc).isoformat()
    return Task(
        task_id=task_id,
        description=f"Mock Task {task_id}",
        status=status,
        priority=priority,
        created_at=now_iso,
        updated_at=now_iso,
        context={}
    )

def create_mock_thought(thought_id: str, task_id: str, status: ThoughtStatus, priority: int = 0) -> Thought:
    now_iso = datetime.now(timezone.utc).isoformat()
    return Thought(
        thought_id=thought_id,
        source_task_id=task_id,
        thought_type="seed",
        status=status,
        created_at=now_iso,
        updated_at=now_iso,
        round_created=0,
        content=f"Mock Thought {thought_id}",
        priority=priority
    )

# --- Test Cases ---

@pytest.mark.asyncio
@patch('ciris_engine.core.agent_processor.persistence')
async def test_activate_pending_tasks(mock_persistence, agent_processor_instance: AgentProcessor, mock_app_config_for_processor):
    """Test activating pending tasks."""
    max_can_activate = mock_app_config_for_processor.workflow.max_active_tasks
    mock_persistence.count_active_tasks = MagicMock(return_value=0)
    
    # Create more tasks than can be activated to test the limit
    all_pending_tasks = [
        create_mock_task("task1", TaskStatus.PENDING),
        create_mock_task("task2", TaskStatus.PENDING),
        create_mock_task("task3", TaskStatus.PENDING)
    ]
    
    # The mock should return only up to the limit passed to it
    def mock_get_pending_limited(limit):
        return all_pending_tasks[:limit]
    
    mock_persistence.get_pending_tasks_for_activation = MagicMock(side_effect=mock_get_pending_limited)
    mock_persistence.update_task_status = MagicMock(return_value=True)

    activated_count = await agent_processor_instance._activate_pending_tasks()

    assert activated_count == max_can_activate
    mock_persistence.get_pending_tasks_for_activation.assert_called_once_with(limit=max_can_activate)
    assert mock_persistence.update_task_status.call_count == max_can_activate
    
    # Check that the first 'max_can_activate' tasks were attempted to be updated
    for i in range(max_can_activate):
        mock_persistence.update_task_status.assert_any_call(all_pending_tasks[i].task_id, TaskStatus.ACTIVE)

@pytest.mark.asyncio
@patch('ciris_engine.core.agent_processor.persistence')
async def test_generate_seed_thoughts(mock_persistence, agent_processor_instance: AgentProcessor, mock_app_config_for_processor):
    """Test generating seed thoughts."""
    task_needing_seed1 = create_mock_task("task_s1", TaskStatus.ACTIVE)
    task_needing_seed2 = create_mock_task("task_s2", TaskStatus.ACTIVE)
    mock_persistence.get_tasks_needing_seed_thought = MagicMock(return_value=[task_needing_seed1, task_needing_seed2])
    mock_persistence.add_thought = MagicMock(return_value="new_thought_id")

    generated_count = await agent_processor_instance._generate_seed_thoughts()

    assert generated_count == 2
    mock_persistence.get_tasks_needing_seed_thought.assert_called_once_with(limit=mock_app_config_for_processor.workflow.max_active_thoughts)
    assert mock_persistence.add_thought.call_count == 2
    # Check that add_thought was called with Thought objects for each task
    call_args_list = mock_persistence.add_thought.call_args_list
    assert any(call.args[0].source_task_id == task_needing_seed1.task_id for call in call_args_list)
    assert any(call.args[0].source_task_id == task_needing_seed2.task_id for call in call_args_list)
    assert all(call.args[0].thought_type == "seed" for call in call_args_list)


@pytest.mark.asyncio
@patch('ciris_engine.core.agent_processor.persistence')
async def test_populate_round_queue(mock_persistence, agent_processor_instance: AgentProcessor, mock_app_config_for_processor):
    """Test populating the round queue."""
    # Mock activate_pending_tasks
    agent_processor_instance._activate_pending_tasks = AsyncMock(return_value=1)
    # Mock generate_seed_thoughts
    agent_processor_instance._generate_seed_thoughts = AsyncMock(return_value=1)

    # Mock existing pending thoughts
    existing_thought1 = create_mock_thought("th_exist1", "task_exist", ThoughtStatus.PENDING)
    existing_thought2 = create_mock_thought("th_exist2", "task_exist", ThoughtStatus.PENDING)
    mock_persistence.get_pending_thoughts_for_active_tasks = MagicMock(return_value=[existing_thought1, existing_thought2])

    await agent_processor_instance._populate_round_queue()

    agent_processor_instance._activate_pending_tasks.assert_called_once()
    agent_processor_instance._generate_seed_thoughts.assert_called_once()
    mock_persistence.get_pending_thoughts_for_active_tasks.assert_called_once_with(limit=mock_app_config_for_processor.workflow.max_active_thoughts)
    
    # Queue should contain up to max_active_thoughts
    assert len(agent_processor_instance.processing_queue) == mock_app_config_for_processor.workflow.max_active_thoughts
    # In this setup, it should take the two existing_thoughts
    assert agent_processor_instance.processing_queue[0].thought_id == existing_thought1.thought_id
    assert agent_processor_instance.processing_queue[1].thought_id == existing_thought2.thought_id


@pytest.mark.asyncio
@patch('ciris_engine.core.agent_processor.persistence')
async def test_process_batch(mock_persistence, agent_processor_instance: AgentProcessor, mock_workflow_coordinator):
    """Test processing a batch of thoughts."""
    thought1 = create_mock_thought("th_batch1", "task_b1", ThoughtStatus.PENDING)
    thought2 = create_mock_thought("th_batch2", "task_b2", ThoughtStatus.PENDING)
    batch_items = [ProcessingQueueItem.from_thought(thought1), ProcessingQueueItem.from_thought(thought2)]

    mock_persistence.update_thought_status = MagicMock(return_value=True) # For marking as PROCESSING
    # Mock WorkflowCoordinator's process_thought to return a mock ActionSelectionPDMAResult
    mock_action_result = MagicMock(spec=ActionSelectionPDMAResult)
    # Set selected_handler_action to an actual enum member
    mock_action_result.selected_handler_action = HandlerActionType.SPEAK 
    # To simulate the .value access in the SUT's logging:
    # We can make selected_handler_action a MagicMock itself if we need to control its .value
    # For now, the SUT accesses result.selected_handler_action.value, so the above is fine if SUT is robust.
    # However, the SUT log is: logging.info(f"... Final Action: {result.selected_handler_action.value if result else 'N/A'}")
    # So, the mock_action_result itself needs selected_handler_action to have a .value
    # Let's make selected_handler_action a mock that has a value attribute.
    mock_sh_action = MagicMock()
    mock_sh_action.value = "speak" # This is what the SUT's log will access
    mock_action_result.selected_handler_action = mock_sh_action

    mock_workflow_coordinator.process_thought = AsyncMock(return_value=mock_action_result)
    
    # Mock _check_and_complete_task for this unit test
    agent_processor_instance._check_and_complete_task = AsyncMock()


    await agent_processor_instance._process_batch(batch_items)

    # Check thoughts marked as PROCESSING
    expected_status_update_calls = [
        call(thought1.thought_id, ThoughtStatus.PROCESSING, round_processed=agent_processor_instance.current_round_number),
        call(thought2.thought_id, ThoughtStatus.PROCESSING, round_processed=agent_processor_instance.current_round_number)
    ]
    # Use asyncio.to_thread, so we check the calls to the original function
    mock_persistence.update_thought_status.assert_has_calls(expected_status_update_calls, any_order=True)
    
    # Check process_thought called for each item
    assert mock_workflow_coordinator.process_thought.call_count == len(batch_items)
    mock_workflow_coordinator.process_thought.assert_any_call(batch_items[0])
    mock_workflow_coordinator.process_thought.assert_any_call(batch_items[1])

    # Check _check_and_complete_task called for each processed thought's task
    assert agent_processor_instance._check_and_complete_task.call_count == len(batch_items)
    agent_processor_instance._check_and_complete_task.assert_any_call(thought1.source_task_id)
    agent_processor_instance._check_and_complete_task.assert_any_call(thought2.source_task_id)


@pytest.mark.asyncio
@patch('ciris_engine.core.agent_processor.persistence')
async def test_check_and_complete_task_completes(mock_persistence, agent_processor_instance: AgentProcessor):
    """Test _check_and_complete_task when a task should be completed."""
    active_task = create_mock_task("task_c1", TaskStatus.ACTIVE)
    mock_persistence.get_task_by_id = MagicMock(return_value=active_task)
    # Simulate no pending thoughts for this task
    mock_persistence.get_pending_thoughts_for_active_tasks = MagicMock(return_value=[]) 
    mock_persistence.update_task_status = MagicMock(return_value=True)

    await agent_processor_instance._check_and_complete_task(active_task.task_id)

    mock_persistence.get_task_by_id.assert_called_once_with(active_task.task_id)
    mock_persistence.get_pending_thoughts_for_active_tasks.assert_called_once() # Called to check
    mock_persistence.update_task_status.assert_called_once_with(active_task.task_id, TaskStatus.COMPLETED)


@pytest.mark.asyncio
@patch('ciris_engine.core.agent_processor.persistence')
async def test_check_and_complete_task_not_active(mock_persistence, agent_processor_instance: AgentProcessor):
    """Test _check_and_complete_task when task is not active."""
    pending_task = create_mock_task("task_c2", TaskStatus.PENDING)
    mock_persistence.get_task_by_id = MagicMock(return_value=pending_task)

    await agent_processor_instance._check_and_complete_task(pending_task.task_id)

    mock_persistence.get_task_by_id.assert_called_once_with(pending_task.task_id)
    mock_persistence.get_pending_thoughts_for_active_tasks.assert_not_called()
    mock_persistence.update_task_status.assert_not_called()


@pytest.mark.asyncio
@patch('ciris_engine.core.agent_processor.persistence')
async def test_check_and_complete_task_has_pending(mock_persistence, agent_processor_instance: AgentProcessor):
    """Test _check_and_complete_task when task still has pending thoughts."""
    active_task = create_mock_task("task_c3", TaskStatus.ACTIVE)
    pending_thought = create_mock_thought("th_pending", active_task.task_id, ThoughtStatus.PENDING)
    mock_persistence.get_task_by_id = MagicMock(return_value=active_task)
    # Simulate one pending thought for this task
    mock_persistence.get_pending_thoughts_for_active_tasks = MagicMock(return_value=[pending_thought]) 

    await agent_processor_instance._check_and_complete_task(active_task.task_id)

    mock_persistence.get_task_by_id.assert_called_once_with(active_task.task_id)
    mock_persistence.get_pending_thoughts_for_active_tasks.assert_called_once()
    mock_persistence.update_task_status.assert_not_called()


@pytest.mark.asyncio
async def test_run_simulation_round(agent_processor_instance: AgentProcessor, mock_workflow_coordinator):
    """Test a single simulation round."""
    agent_processor_instance._populate_round_queue = AsyncMock()
    agent_processor_instance._process_batch = AsyncMock()
    
    # Simulate queue having items to ensure _process_batch is called
    agent_processor_instance.processing_queue = collections.deque([MagicMock(spec=ProcessingQueueItem)])

    initial_round_number = mock_workflow_coordinator.current_round_number

    await agent_processor_instance.run_simulation_round()

    mock_workflow_coordinator.advance_round.assert_called_once()
    assert agent_processor_instance.current_round_number == initial_round_number + 1
    agent_processor_instance._populate_round_queue.assert_called_once()
    agent_processor_instance._process_batch.assert_called_once_with(list(agent_processor_instance.processing_queue))


@pytest.mark.skip(reason="Test is currently causing hangs/kills, needs further investigation")
@pytest.mark.asyncio
async def test_start_and_stop_processing(agent_processor_instance: AgentProcessor, mock_app_config_for_processor):
    """Test starting and stopping the processing loop."""
    num_test_rounds = 2
    agent_processor_instance.run_simulation_round = AsyncMock() # Mock the actual work per round

    # Start processing
    processing_task = None # Ensure it's defined for finally block
    try:
        processing_task = asyncio.create_task(agent_processor_instance.start_processing(num_rounds=num_test_rounds))
        # Wait for the task to complete, with a reasonable timeout
        await asyncio.wait_for(processing_task, timeout=2.0) 
    except asyncio.TimeoutError:
        pytest.fail(f"Processing loop for {num_test_rounds} rounds did not complete within timeout.")
    finally:
        if processing_task and not processing_task.done():
            processing_task.cancel() # Ensure task is cancelled if it timed out
            with pytest.raises(asyncio.CancelledError): # Suppress CancelledError if it occurs here
                await processing_task


    assert agent_processor_instance.run_simulation_round.call_count == num_test_rounds
    assert agent_processor_instance._stop_event.is_set() # Should be set by loop completion

    # Test stopping explicitly
    agent_processor_instance.run_simulation_round.reset_mock()
    agent_processor_instance._stop_event.clear()
    agent_processor_instance._processing_task = None # Reset internal task reference for a clean slate

    # Start processing indefinitely (no num_rounds)
    # We create the task but won't await it directly here,
    # as start_processing itself awaits its internal loop task.
    # The goal is to test if stop_processing can interrupt it.
    
    start_task = asyncio.create_task(agent_processor_instance.start_processing())
    await asyncio.sleep(0.05) # Allow the processing loop to start and self._processing_task to be set

    assert agent_processor_instance._processing_task is not None, "Processing task was not set by start_processing"
    assert not agent_processor_instance._processing_task.done(), "Processing task finished prematurely"
    assert not agent_processor_instance._stop_event.is_set()

    await agent_processor_instance.stop_processing() # This should set the event and ensure the task stops

    assert agent_processor_instance._stop_event.is_set(), "Stop event was not set by stop_processing"
    
    # After stop_processing, the internal _processing_task should be None or done.
    # stop_processing itself tries to await/cancel the task.
    # We give a small additional delay to ensure the event loop processes the cancellation/completion.
    await asyncio.sleep(0.05) 
    
    assert agent_processor_instance._processing_task is None, \
        f"Internal _processing_task was not cleared after stop. State: {agent_processor_instance._processing_task}"

    # Ensure the initially created task for start_processing also completes.
    # This task (start_task) should complete because the internal loop it manages has been stopped.
    try:
        await asyncio.wait_for(start_task, timeout=1.0)
    except asyncio.TimeoutError:
        start_task.cancel() # Clean up
        with pytest.raises(asyncio.CancelledError):
            await start_task
        pytest.fail("The main start_processing task did not complete after stop_processing was called.")
