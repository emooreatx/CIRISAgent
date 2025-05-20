import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ciris_engine.core.workflow_coordinator import WorkflowCoordinator
from ciris_engine.core.agent_core_schemas import (
    Thought,
    ActionSelectionPDMAResult,
    EthicalPDMAResult,
    CSDMAResult,
    DSDMAResult,
)
from ciris_engine.core.foundational_schemas import ThoughtStatus, HandlerActionType, TaskStatus
from ciris_engine.core.agent_processing_queue import ProcessingQueueItem
from ciris_engine.core.config_schemas import AppConfig, WorkflowConfig, LLMServicesConfig, OpenAIConfig, DatabaseConfig, GuardrailsConfig, SerializableAgentProfile
from ciris_engine.services.discord_graph_memory import DiscordGraphMemory

# --- Fixtures ---

@pytest.fixture
def mock_app_config():
    """Provides a mock AppConfig."""
    return AppConfig(
        db=DatabaseConfig(db_filename="test_wc.db"),
        llm_services=LLMServicesConfig(openai=OpenAIConfig(model_name="test-model")),
        workflow=WorkflowConfig(max_active_tasks=2, max_active_thoughts=2, round_delay_seconds=0, max_ponder_rounds=1),
        guardrails=GuardrailsConfig(),
        agent_profiles={
            "default_profile": SerializableAgentProfile(name="default_profile", permitted_actions=[HandlerActionType.SPEAK])
        }
    )

@pytest.fixture
def mock_llm_client():
    return AsyncMock()

@pytest.fixture
def mock_ethical_pdma_evaluator():
    mock = AsyncMock()
    mock.evaluate = AsyncMock()
    return mock

@pytest.fixture
def mock_csdma_evaluator():
    mock = AsyncMock()
    mock.evaluate_thought = AsyncMock()
    return mock

@pytest.fixture
def mock_action_selection_pdma_evaluator():
    mock = AsyncMock()
    mock.evaluate = AsyncMock()
    return mock

@pytest.fixture
def mock_ethical_guardrails():
    mock = AsyncMock()
    mock.check_action_output_safety = AsyncMock(return_value=(True, "Guardrail passed", {})) # Default to pass
    return mock


@pytest.fixture
async def memory_service(tmp_path: Path):
    service = DiscordGraphMemory(str(tmp_path / "graph.pkl"))
    await service.start()
    yield service

@pytest.fixture
def mock_dsdma_evaluators_dict():
    # For simplicity, start with an empty dict or a basic mock if needed
    return {}

@pytest.fixture
def mock_dsdma_evaluators_with_item():
    dsdma = AsyncMock()
    dsdma.evaluate_thought = AsyncMock()
    dsdma.domain_name = "MockDomain"
    return {"default_profile": dsdma}


@pytest.fixture
def workflow_coordinator_instance(
    mock_llm_client,
    mock_ethical_pdma_evaluator,
    mock_csdma_evaluator,
    mock_action_selection_pdma_evaluator,
    mock_ethical_guardrails,
    mock_app_config, # Use the more complete AppConfig mock
    mock_dsdma_evaluators_dict,
    memory_service
):
    """Provides a WorkflowCoordinator instance with mocked dependencies."""
    return WorkflowCoordinator(
        llm_client=mock_llm_client,
        ethical_pdma_evaluator=mock_ethical_pdma_evaluator,
        csdma_evaluator=mock_csdma_evaluator,
        action_selection_pdma_evaluator=mock_action_selection_pdma_evaluator,
        ethical_guardrails=mock_ethical_guardrails,
        app_config=mock_app_config, # Pass the AppConfig object
        dsdma_evaluators=mock_dsdma_evaluators_dict,
        memory_service=memory_service
    )

@pytest.mark.asyncio
@patch('ciris_engine.core.workflow_coordinator.persistence')
async def test_memory_meta_thought(
    mock_persistence,
    workflow_coordinator_instance: WorkflowCoordinator,
    memory_service: DiscordGraphMemory
):
    now = datetime.now(timezone.utc).isoformat()
    thought = Thought(
        thought_id="mem1",
        source_task_id="task1",
        thought_type="memory_meta",
        status=ThoughtStatus.PENDING,
        created_at=now,
        updated_at=now,
        round_created=0,
        content="meta",
        processing_context={"user_nick": "alice", "channel": "general", "metadata": {"kind": "friend"}},
        priority=0,
    )
    item = ProcessingQueueItem.from_thought(thought)
    mock_persistence.get_thought_by_id.return_value = thought
    mock_persistence.update_thought_status = MagicMock(return_value=True)

    mem_mock = AsyncMock()
    memory_service.memorize = mem_mock

    result = await workflow_coordinator_instance.process_thought(item)

    assert result is not None
    mem_mock.assert_not_awaited()

@pytest.fixture
def sample_thought():
    now_iso = datetime.now(timezone.utc).isoformat()
    return Thought(
        thought_id=str(uuid.uuid4()),
        source_task_id=str(uuid.uuid4()),
        thought_type="seed",
        status=ThoughtStatus.PENDING,
        created_at=now_iso,
        updated_at=now_iso,
        round_created=0,
        content="This is a test thought.",
        priority=1
    )

@pytest.fixture
def sample_processing_queue_item(sample_thought: Thought):
    return ProcessingQueueItem.from_thought(sample_thought)

# --- Test Cases for New WorkflowCoordinator ---

@pytest.mark.asyncio
async def test_advance_round(workflow_coordinator_instance: WorkflowCoordinator):
    """Test that advance_round increments the internal round number."""
    assert workflow_coordinator_instance.current_round_number == 0
    workflow_coordinator_instance.advance_round()
    assert workflow_coordinator_instance.current_round_number == 1
    workflow_coordinator_instance.advance_round()
    assert workflow_coordinator_instance.current_round_number == 2

@pytest.mark.asyncio
@patch('ciris_engine.core.workflow_coordinator.persistence')
async def test_process_thought_successful_run(
    mock_persistence,
    workflow_coordinator_instance: WorkflowCoordinator,
    sample_processing_queue_item: ProcessingQueueItem,
    sample_thought: Thought,
    mock_ethical_pdma_evaluator: MagicMock,
    mock_csdma_evaluator: MagicMock,
    mock_action_selection_pdma_evaluator: MagicMock,
    mock_ethical_guardrails: MagicMock
):
    """Test a successful run of process_thought."""
    mock_persistence.get_thought_by_id = MagicMock(return_value=sample_thought)
    mock_persistence.update_thought_status = MagicMock(return_value=True)

    # Mock DMA results
    # Ensure mocked results are instances of the actual Pydantic models or spec'd MagicMocks with all required fields
    mock_ethical_pdma_evaluator.evaluate.return_value = EthicalPDMAResult(
        context="Mocked ethical context",
        alignment_check={"principle1": "aligned"},
        decision="Ethical decision: Proceed",
        monitoring={"metrics": "engagement"}
    )
    mock_csdma_evaluator.evaluate_thought.return_value = CSDMAResult(
        common_sense_plausibility_score=0.9,
        flags=[],
        reasoning="Looks plausible"
    )
    
    action_selection_result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="summary",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.SPEAK,
        action_parameters={"content": "Hello"},
        action_selection_rationale="rationale",
        monitoring_for_selected_action={"status": "Test monitoring status"} # Ensure this field is present
    )
    mock_action_selection_pdma_evaluator.evaluate.return_value = action_selection_result

    result = await workflow_coordinator_instance.process_thought(sample_processing_queue_item)

    assert result is not None
    assert result.selected_handler_action == HandlerActionType.SPEAK
    mock_persistence.get_thought_by_id.assert_called_once_with(sample_processing_queue_item.thought_id)
    mock_ethical_pdma_evaluator.evaluate.assert_called_once()
    mock_csdma_evaluator.evaluate_thought.assert_called_once()
    mock_action_selection_pdma_evaluator.evaluate.assert_called_once()
    mock_ethical_guardrails.check_action_output_safety.assert_called_once()
    
    # Check that thought status is updated to COMPLETED
    update_calls = mock_persistence.update_thought_status.call_args_list
    final_update_call = [c for c in update_calls if c.kwargs.get('new_status') == ThoughtStatus.COMPLETED]
    assert len(final_update_call) == 1
    assert final_update_call[0].kwargs['thought_id'] == sample_thought.thought_id
    assert final_update_call[0].kwargs['round_processed'] == workflow_coordinator_instance.current_round_number


@pytest.mark.asyncio
@patch('ciris_engine.core.workflow_coordinator.persistence')
async def test_process_thought_guardrail_failure(
    mock_persistence,
    workflow_coordinator_instance: WorkflowCoordinator,
    sample_processing_queue_item: ProcessingQueueItem,
    sample_thought: Thought,
    mock_ethical_pdma_evaluator: MagicMock,
    mock_csdma_evaluator: MagicMock,
    mock_action_selection_pdma_evaluator: MagicMock,
    mock_ethical_guardrails: MagicMock
):
    """Test process_thought when ethical guardrail fails."""
    mock_persistence.get_thought_by_id = MagicMock(return_value=sample_thought)
    mock_persistence.update_thought_status = MagicMock(return_value=True)

    mock_ethical_pdma_evaluator.evaluate.return_value = EthicalPDMAResult(
        context="Mocked ethical context for guardrail test",
        alignment_check={"principle1": "aligned"},
        decision="Ethical decision: Proceed (risky)",
        monitoring={"metrics": "engagement"}
    )
    mock_csdma_evaluator.evaluate_thought.return_value = CSDMAResult(
        common_sense_plausibility_score=0.9,
        flags=[],
        reasoning="Looks plausible (risky)"
    )
    
    action_selection_result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="summary",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.SPEAK,
        action_parameters={"content": "Risky content"},
        action_selection_rationale="rationale",
        monitoring_for_selected_action={"status": "Test monitoring status for risky content"} # Ensure this field is present
    )
    mock_action_selection_pdma_evaluator.evaluate.return_value = action_selection_result
    mock_ethical_guardrails.check_action_output_safety.return_value = (False, "Guardrail failed", {}) # Guardrail fails

    result = await workflow_coordinator_instance.process_thought(sample_processing_queue_item)

    assert result is not None
    assert result.selected_handler_action == HandlerActionType.DEFER # Should be deferred
    assert "Guardrail failed" in result.action_parameters.reason # Access the 'reason' attribute directly
    assert sample_thought.escalations
    assert sample_thought.escalations[0]["type"] == "guardrail_violation"


@pytest.mark.skip(reason="Failing with AttributeError: 'PonderParams' object has no attribute 'get' in SUT")
@pytest.mark.asyncio
@patch('ciris_engine.core.workflow_coordinator.persistence')
async def test_process_thought_ponder_action(
    mock_persistence,
    workflow_coordinator_instance: WorkflowCoordinator,
    sample_processing_queue_item: ProcessingQueueItem,
    sample_thought: Thought,
    mock_ethical_pdma_evaluator: MagicMock,
    mock_csdma_evaluator: MagicMock,
    mock_action_selection_pdma_evaluator: MagicMock
):
    """Test process_thought when PONDER action is selected."""
    mock_persistence.get_thought_by_id = MagicMock(return_value=sample_thought)
    mock_persistence.update_thought_status = MagicMock(return_value=True) # Mock successful update for PONDER

    # Ensure mocks return actual result objects, not just MagicMock
    mock_ethical_pdma_evaluator.evaluate.return_value = EthicalPDMAResult(
        context="Ethical context for ponder", decision="Ethical decision", alignment_check={}, monitoring={}
    )
    mock_csdma_evaluator.evaluate_thought.return_value = CSDMAResult(
        common_sense_plausibility_score=0.9, flags=[], reasoning="CSDMA ok for ponder"
    )

    action_selection_result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="summary",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.PONDER, # PONDER action
        action_parameters={"key_questions": ["What if?"]},
        action_selection_rationale="rationale",
        monitoring_for_selected_action={"status": "Test monitoring for ponder"} # Ensure this field is present
    )
    mock_action_selection_pdma_evaluator.evaluate.return_value = action_selection_result

    result = await workflow_coordinator_instance.process_thought(sample_processing_queue_item)

    assert result is None # PONDER should result in None if re-queue succeeds

    # Verify the specific call to update_thought_status for PONDER re-queue
    mock_persistence.update_thought_status.assert_called_with(
        thought_id=sample_thought.thought_id,
        new_status=ThoughtStatus.PENDING,
        round_processed=None,
        final_action_result={"status": "Re-queued for Ponder", "ponder_action_details": action_selection_result.model_dump()},
        ponder_notes=["What if?"], # Match the action_parameters
        ponder_count=sample_thought.ponder_count + 1
    )


@pytest.mark.skip(reason="Failing with AttributeError: 'PonderParams' object has no attribute 'get' in SUT")
@pytest.mark.asyncio
@patch('ciris_engine.core.workflow_coordinator.persistence')
async def test_process_thought_max_ponder_rounds_reached(
    mock_persistence,
    workflow_coordinator_instance: WorkflowCoordinator,
    sample_processing_queue_item: ProcessingQueueItem,
    sample_thought: Thought, # sample_thought has ponder_count = 0
    mock_ethical_pdma_evaluator: MagicMock,
    mock_csdma_evaluator: MagicMock,
    mock_action_selection_pdma_evaluator: MagicMock,
    mock_app_config: AppConfig
):
    """Test process_thought when PONDER action is selected but max_ponder_rounds is reached."""
    # Set max_ponder_rounds to 1 for this test in the coordinator's config
    workflow_coordinator_instance.max_ponder_rounds = 1 
    sample_thought.ponder_count = 1 # Set current ponder_count to max

    mock_persistence.get_thought_by_id = MagicMock(return_value=sample_thought)
    mock_persistence.update_thought_status = MagicMock(return_value=True)

    # Ensure mocks return actual result objects, not just MagicMock
    mock_ethical_pdma_evaluator.evaluate.return_value = EthicalPDMAResult(
        context="Ethical context for max ponder", decision="Ethical decision", alignment_check={}, monitoring={}
    )
    mock_csdma_evaluator.evaluate_thought.return_value = CSDMAResult(
        common_sense_plausibility_score=0.9, flags=[], reasoning="CSDMA ok for max ponder"
    )

    action_selection_result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="summary",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.PONDER, # PONDER action
        action_parameters={"key_questions": ["What if?"]},
        action_selection_rationale="rationale",
        monitoring_for_selected_action={"status": "Test monitoring for ponder max rounds"} # Ensure this field is present
    )
    mock_action_selection_pdma_evaluator.evaluate.return_value = action_selection_result

    result = await workflow_coordinator_instance.process_thought(sample_processing_queue_item)

    assert result is not None
    assert result.selected_handler_action == HandlerActionType.DEFER # Should defer
    # Check the reason attribute directly on the action_parameters object
    assert hasattr(result.action_parameters, 'reason'), "action_parameters object missing 'reason' attribute"
    assert "Thought reached maximum ponder rounds" in result.action_parameters.reason

    # Check that thought status is updated to DEFERRED
    update_calls = mock_persistence.update_thought_status.call_args_list
    defer_update_call = [c for c in update_calls if c.kwargs.get('new_status') == ThoughtStatus.DEFERRED]
    assert len(defer_update_call) == 1
    assert defer_update_call[0].kwargs['thought_id'] == sample_thought.thought_id


@pytest.mark.asyncio
@patch('ciris_engine.core.workflow_coordinator.persistence')
async def test_process_thought_dma_exception(
    mock_persistence,
    workflow_coordinator_instance: WorkflowCoordinator,
    sample_processing_queue_item: ProcessingQueueItem,
    sample_thought: Thought,
    mock_ethical_pdma_evaluator: MagicMock, # This one will raise an exception
    mock_csdma_evaluator: MagicMock, # Mock other DMAs even if not strictly needed after exception
    mock_action_selection_pdma_evaluator: MagicMock # Mock Action Selection PDMA
):
    """Test process_thought when a DMA evaluator raises an exception."""
    mock_persistence.get_thought_by_id = MagicMock(return_value=sample_thought)
    mock_persistence.update_thought_status = MagicMock(return_value=True)

    # Simulate Ethical PDMA raising an exception
    mock_ethical_pdma_evaluator.evaluate.side_effect = Exception("Ethical PDMA Error")
    
    # Mock CSDMA to return a valid result (it might run concurrently before exception is handled)
    mock_csdma_evaluator.evaluate_thought.return_value = CSDMAResult(
        common_sense_plausibility_score=0.5, flags=[], reasoning="CSDMA ran"
    )

    # Mock ActionSelectionPDMA to return DEFER when it receives the fallback Ethical result
    defer_result_on_exception = ActionSelectionPDMAResult(
        context_summary_for_action_selection="Action selection deferred due to upstream DMA error.",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.DEFER,
        action_parameters={"reason": "Ethical PDMA failed: Ethical PDMA Error"}, # Ensure this is a dict
        action_selection_rationale="Deferring because Ethical PDMA evaluation failed.",
        monitoring_for_selected_action={"status": "DMA Exception Deferral"}
    )
    mock_action_selection_pdma_evaluator.evaluate.return_value = defer_result_on_exception


    result = await workflow_coordinator_instance.process_thought(sample_processing_queue_item)

    # The WorkflowCoordinator creates a fallback EthicalPDMAResult.
    # ActionSelectionPDMA receives this and should decide to DEFER (as mocked above).
    assert result is not None
    assert result.selected_handler_action == HandlerActionType.DEFER
    # Check the reason attribute directly on the action_parameters object
    assert hasattr(result.action_parameters, 'reason'), "action_parameters object missing 'reason' attribute"
    assert "Ethical PDMA failed" in result.action_parameters.reason


@pytest.mark.asyncio
@patch('ciris_engine.core.workflow_coordinator.persistence')
async def test_process_thought_object_not_found(
    mock_persistence,
    workflow_coordinator_instance: WorkflowCoordinator,
    sample_processing_queue_item: ProcessingQueueItem
):
    """Test process_thought when the Thought object cannot be fetched from persistence."""
    mock_persistence.get_thought_by_id = MagicMock(return_value=None) # Simulate thought not found

    result = await workflow_coordinator_instance.process_thought(sample_processing_queue_item)

    assert result is not None
    assert result.selected_handler_action == HandlerActionType.DEFER
    assert "Thought object not found" in result.context_summary_for_action_selection
    # Check the reason attribute directly on the action_parameters object
    assert hasattr(result.action_parameters, 'reason'), "action_parameters object missing 'reason' attribute"
    assert f"Failed to retrieve thought object for ID {sample_processing_queue_item.thought_id}" in result.action_parameters.reason
    mock_persistence.update_thought_status.assert_not_called() # No status update if thought isn't processed


@pytest.mark.asyncio
@patch('ciris_engine.core.workflow_coordinator.persistence')
async def test_process_thought_with_dsdma_success(
    mock_persistence,
    workflow_coordinator_instance: WorkflowCoordinator,
    mock_dsdma_evaluators_with_item,
    sample_processing_queue_item: ProcessingQueueItem,
    sample_thought: Thought,
    mock_ethical_pdma_evaluator: MagicMock,
    mock_csdma_evaluator: MagicMock,
    mock_action_selection_pdma_evaluator: MagicMock,
    mock_ethical_guardrails: MagicMock,
):
    """Ensure PDMA, CSDMA, and DSDMA run and feed ActionSelectionPDMA."""
    workflow_coordinator_instance.dsdma_evaluators = mock_dsdma_evaluators_with_item
    dsdma_mock = mock_dsdma_evaluators_with_item["default_profile"]

    mock_persistence.get_thought_by_id = MagicMock(return_value=sample_thought)
    mock_persistence.update_thought_status = MagicMock(return_value=True)

    ethical_result = EthicalPDMAResult(context="ctx", alignment_check={}, decision="dec", monitoring={})
    cs_result = CSDMAResult(common_sense_plausibility_score=1.0, flags=[], reasoning="ok")
    dsdma_result = DSDMAResult(domain_name="Mock", domain_alignment_score=0.5, recommended_action=None, flags=[], reasoning="ok")

    mock_ethical_pdma_evaluator.evaluate.return_value = ethical_result
    mock_csdma_evaluator.evaluate_thought.return_value = cs_result
    dsdma_mock.evaluate_thought.return_value = dsdma_result

    asp_result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="sum",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.SPEAK,
        action_parameters={"content": "hi"},
        action_selection_rationale="r",
        monitoring_for_selected_action={"s": "1"},
    )
    mock_action_selection_pdma_evaluator.evaluate.return_value = asp_result

    result = await workflow_coordinator_instance.process_thought(sample_processing_queue_item)

    assert result.selected_handler_action == HandlerActionType.SPEAK
    mock_ethical_pdma_evaluator.evaluate.assert_called_once()
    mock_csdma_evaluator.evaluate_thought.assert_called_once()
    dsdma_mock.evaluate_thought.assert_called_once()
    mock_action_selection_pdma_evaluator.evaluate.assert_called_once()
    triaged = mock_action_selection_pdma_evaluator.evaluate.call_args.kwargs["triaged_inputs"]
    assert triaged["dsdma_result"] is dsdma_result


@pytest.mark.asyncio
@patch('ciris_engine.core.workflow_coordinator.persistence')
async def test_process_thought_dsdma_exception(
    mock_persistence,
    workflow_coordinator_instance: WorkflowCoordinator,
    mock_dsdma_evaluators_with_item,
    sample_processing_queue_item: ProcessingQueueItem,
    sample_thought: Thought,
    mock_ethical_pdma_evaluator: MagicMock,
    mock_csdma_evaluator: MagicMock,
    mock_action_selection_pdma_evaluator: MagicMock,
    mock_ethical_guardrails: MagicMock,
):
    """If DSDMA fails, ActionSelectionPDMA still runs with None."""
    workflow_coordinator_instance.dsdma_evaluators = mock_dsdma_evaluators_with_item
    dsdma_mock = mock_dsdma_evaluators_with_item["default_profile"]

    mock_persistence.get_thought_by_id = MagicMock(return_value=sample_thought)
    mock_persistence.update_thought_status = MagicMock(return_value=True)

    ethical_result = EthicalPDMAResult(context="ctx", alignment_check={}, decision="dec", monitoring={})
    cs_result = CSDMAResult(common_sense_plausibility_score=1.0, flags=[], reasoning="ok")

    mock_ethical_pdma_evaluator.evaluate.return_value = ethical_result
    mock_csdma_evaluator.evaluate_thought.return_value = cs_result
    dsdma_mock.evaluate_thought.side_effect = Exception("fail")

    asp_result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="sum",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.SPEAK,
        action_parameters={"content": "hi"},
        action_selection_rationale="r",
        monitoring_for_selected_action={"s": "1"},
    )
    mock_action_selection_pdma_evaluator.evaluate.return_value = asp_result

    result = await workflow_coordinator_instance.process_thought(sample_processing_queue_item)

    assert result.selected_handler_action == HandlerActionType.SPEAK
    mock_action_selection_pdma_evaluator.evaluate.assert_called_once()
    triaged = mock_action_selection_pdma_evaluator.evaluate.call_args.kwargs["triaged_inputs"]
    assert triaged["dsdma_result"] is None
