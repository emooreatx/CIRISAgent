import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import uuid
from datetime import datetime, timezone

from ciris_engine.core import persistence
from ciris_engine.config.config_manager import get_config_async, AppConfig
from ciris_engine.utils.profile_loader import load_profile # AgentProfile will be imported from config_schemas
from ciris_engine.schemas.config_schemas_v1 import SerializableAgentProfile as AgentProfile # Correct import
from ciris_engine.core.agent_processing_queue import ProcessingQueueItem # Added import
from ciris_engine.services.llm_service import LLMService
from ciris_engine.memory.ciris_local_graph import CIRISLocalGraph
from ciris_engine.dma.pdma import EthicalPDMAEvaluator
from ciris_engine.dma.csdma import CSDMAEvaluator
from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAEvaluator
from ciris_engine.guardrails import EthicalGuardrails
from ciris_engine.core.thought_processor import ThoughtProcessor
from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought, DSDMAResult
from ciris_engine.schemas.dma_results_v1 import EthicalPDMAResult, CSDMAResult, ActionSelectionPDMAResult
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus, HandlerActionType
from ciris_engine.schemas.action_params_v1 import SpeakParams
from ciris_engine.utils.context_formatters import format_system_snapshot_for_prompt # For assertion

# Ensure database is initialized for tests that might use it
@pytest.fixture(scope="module", autouse=True) # Changed to synchronous fixture
def initialize_db_module_synchronous(): # Renamed for clarity
    persistence.initialize_database()

@pytest_asyncio.fixture
async def app_config():
    return await get_config_async()

@pytest_asyncio.fixture
async def teacher_profile(app_config: AppConfig):
    profile_path = "ciris_profiles/teacher.yaml"
    profile = await load_profile(profile_path)
    if profile.name.lower() not in app_config.agent_profiles:
        app_config.agent_profiles[profile.name.lower()] = profile
    return profile

@pytest_asyncio.fixture
async def llm_service(app_config: AppConfig):
    service = LLMService(app_config.llm_services)
    await service.start()
    yield service
    await service.stop()

@pytest_asyncio.fixture
async def memory_service():
    service = CIRISLocalGraph() # Using real one, can be mocked if complex
    await service.start()
    yield service
    await service.stop()

@pytest_asyncio.fixture
def ethical_pdma_evaluator(llm_service: LLMService, app_config: AppConfig):
    return EthicalPDMAEvaluator(
        aclient=llm_service.get_client().instruct_client, # instruct_client is already patched
        model_name=llm_service.get_client().model_name,
        max_retries=app_config.llm_services.openai.max_retries
    )

@pytest_asyncio.fixture
def csdma_evaluator(llm_service: LLMService, app_config: AppConfig):
    return CSDMAEvaluator(
        aclient=llm_service.get_client().client, # raw client, CSDMA patches it
        model_name=llm_service.get_client().model_name,
        max_retries=app_config.llm_services.openai.max_retries
    )

@pytest_asyncio.fixture
def action_selection_pdma_evaluator(llm_service: LLMService, app_config: AppConfig, teacher_profile: AgentProfile):
    # ActionSelectionPDMAEvaluator expects a raw client and patches it.
    return ActionSelectionPDMAEvaluator(
        aclient=llm_service.get_client().client, # Pass raw client
        model_name=llm_service.get_client().model_name,
        max_retries=app_config.llm_services.openai.max_retries,
        prompt_overrides=teacher_profile.action_selection_pdma_overrides
    )

@pytest_asyncio.fixture
def ethical_guardrails(llm_service: LLMService, app_config: AppConfig):
    return EthicalGuardrails(
        llm_service.get_client().instruct_client,
        app_config.guardrails,
        model_name=llm_service.get_client().model_name
    )

@pytest_asyncio.fixture
def thought_processor(
    llm_service: LLMService,
    ethical_pdma_evaluator: EthicalPDMAEvaluator,
    csdma_evaluator: CSDMAEvaluator,
    action_selection_pdma_evaluator: ActionSelectionPDMAEvaluator,
    ethical_guardrails: EthicalGuardrails,
    app_config: AppConfig,
    memory_service: CIRISLocalGraph
):
    return ThoughtProcessor(
        dma_orchestrator=AsyncMock(),
        context_builder=AsyncMock(),
        guardrail_orchestrator=AsyncMock(),
        ponder_manager=AsyncMock(),
        app_config=app_config
    )

@pytest.mark.asyncio
async def test_recently_completed_tasks_in_dma_prompts(
    thought_processor: ThoughtProcessor,
    teacher_profile: AgentProfile,
    ethical_pdma_evaluator: EthicalPDMAEvaluator,
    csdma_evaluator: CSDMAEvaluator,
    action_selection_pdma_evaluator: ActionSelectionPDMAEvaluator
):
    # 1. Create a completed task
    completed_task_id = f"task-completed-{uuid.uuid4()}"
    completed_task_desc = "Test Wakeup Ritual Completed"
    completed_task = Task(
        task_id=completed_task_id,
        description=completed_task_desc,
        status=TaskStatus.COMPLETED,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        priority=1
    )
    persistence.add_task(completed_task)

    # 2. Create an active task that will be processed
    active_task_id = f"task-active-{uuid.uuid4()}"
    active_task_desc = "User asks about the Test Wakeup Ritual"
    active_task = Task(
        task_id=active_task_id,
        description=active_task_desc,
        status=TaskStatus.ACTIVE,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        priority=1
    )
    persistence.add_task(active_task)

    # 3. Create a thought for the active task
    thought_id = f"th-{uuid.uuid4()}"
    thought = Thought(
        thought_id=thought_id,
        source_task_id=active_task_id,
        thought_type="initial_query",
        status=ThoughtStatus.PENDING, # Will be set to PROCESSING by build_context
        content=active_task_desc, # Content of the thought
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        round_created=0,
        priority=1
    )
    # Note: build_context will populate processing_context
    # persistence.add_thought(thought) # Not strictly needed if build_context creates/updates it

    # 4. Build context for the thought
    # This will populate thought.processing_context["system_snapshot"]["recently_completed_tasks_summary"]
    # Corrected argument order: (task, thought)
    # build_context returns the system_snapshot dict, not the modified thought object.
    system_snapshot_dict = await thought_processor.build_context(active_task, thought)
    
    # Manually assign the system_snapshot to the thought's processing_context for the test
    if thought.processing_context is None:
        thought.processing_context = {}
    thought.processing_context["system_snapshot"] = system_snapshot_dict
    
    thought_with_context = thought # Now use the original thought object, which has been updated

    assert thought_with_context.processing_context is not None
    assert "system_snapshot" in thought_with_context.processing_context
    assert "recently_completed_tasks_summary" in thought_with_context.processing_context["system_snapshot"]
    
    # Verify the completed task is in the summary (sanity check before mocking)
    found_completed_in_snapshot = False
    # Accessing the summary from the populated thought_with_context
    for task_summary in thought_with_context.processing_context["system_snapshot"]["recently_completed_tasks_summary"]:
        if task_summary.get("task_id") == completed_task_id:
            found_completed_in_snapshot = True
            break
    assert found_completed_in_snapshot, "Completed task not found in system_snapshot's recently_completed_tasks_summary"

    # 5. Mock the LLM calls for each DMA
    mock_ethical_create = AsyncMock(
        return_value=EthicalPDMAResult(
            context="Test context", # Using actual field name
            alignment_check={"do_good": "High"}, # Using actual field name
            decision="Proceed", # Using actual field name
            monitoring={"status": "nominal"} # Using actual field name
            # Optional fields like conflicts, resolution, raw_llm_response will default to None
        )
    )
    mock_csdma_create = AsyncMock(
        return_value=CSDMAResult(
            common_sense_plausibility_score=0.9,
            flags=[],
            reasoning="Looks plausible."
        )
    )
    mock_action_selection_create = AsyncMock(
        return_value=ActionSelectionPDMAResult( # This is the internal _ActionSelectionLLMResponse structure
            context_summary_for_action_selection="Summary",
            action_alignment_check={"SPEAK": "High"},
            selected_handler_action=HandlerActionType.SPEAK,
            action_parameters=SpeakParams(content="Hello!"),
            action_selection_rationale="User asked a question.",
            monitoring_for_selected_action="Monitor response."
        )
    )

    # Patch the 'create' method on the 'chat.completions' attribute of the aclient
    # For EthicalPDMA, aclient is already an instructor client
    # For CSDMA and ActionSelectionPDMA, aclient is patched inside them, so we patch their internal instructor client.
    # We will patch the run_X_dma functions in the thought_processor's namespace.
    
    mock_run_pdma = AsyncMock(return_value=mock_ethical_create.return_value) # Use the same return value
    mock_run_csdma = AsyncMock(return_value=mock_csdma_create.return_value)
    mock_run_action_selection_pdma = AsyncMock(return_value=mock_action_selection_create.return_value)

    with patch('ciris_engine.core.thought_processor.run_pdma', mock_run_pdma), \
         patch('ciris_engine.core.thought_processor.run_csdma', mock_run_csdma), \
         patch('ciris_engine.core.thought_processor.run_action_selection_pdma', mock_run_action_selection_pdma):

        # Create a ProcessingQueueItem for the thought
        processing_item = ProcessingQueueItem(
            thought_id=thought_with_context.thought_id,
            source_task_id=thought_with_context.source_task_id,
            content=thought_with_context.content,
            priority=thought_with_context.priority,
            thought_type=thought_with_context.thought_type,
        )
        
        # Mock persistence.get_thought_by_id to return our thought_with_context
        # when process_thought tries to fetch it.
        # And mock persistence.get_task_by_id for when build_context is called internally.
        with patch('ciris_engine.core.thought_processor.persistence.get_thought_by_id', return_value=thought_with_context), \
             patch('ciris_engine.core.thought_processor.persistence.get_task_by_id', return_value=active_task):
            final_action_result = await thought_processor.process_thought(
                processing_item,
            )
        
        assert final_action_result is not None

    # 7. Assertions: Check the context of the thought object passed to the mocked run_X_dma functions
    expected_recent_task_text = "Recently Completed Tasks (Review for relevant context before responding):"

    # Ethical PDMA (via mock_run_pdma)
    mock_run_pdma.assert_called_once()
    # The second argument to run_pdma is the thought_object
    thought_arg_pdma = mock_run_pdma.call_args[0][1] 
    assert thought_arg_pdma.processing_context is not None
    system_snapshot_pdma = thought_arg_pdma.processing_context.get("system_snapshot", {})
    # Format the snapshot as it would be for the prompt
    prompt_context_pdma = format_system_snapshot_for_prompt(system_snapshot_pdma, thought_arg_pdma.processing_context)
    assert expected_recent_task_text in prompt_context_pdma, "Ethical PDMA context missing recent tasks header"
    assert completed_task_desc in prompt_context_pdma, "Ethical PDMA context missing completed task description"

    # CSDMA (via mock_run_csdma)
    mock_run_csdma.assert_called_once()
    thought_arg_csdma = mock_run_csdma.call_args[0][1]
    assert thought_arg_csdma.processing_context is not None
    system_snapshot_csdma = thought_arg_csdma.processing_context.get("system_snapshot", {})
    prompt_context_csdma = format_system_snapshot_for_prompt(system_snapshot_csdma, thought_arg_csdma.processing_context)
    assert expected_recent_task_text in prompt_context_csdma, "CSDMA context missing recent tasks header"
    assert completed_task_desc in prompt_context_csdma, "CSDMA context missing completed task description"

    # Action Selection PDMA (via mock_run_action_selection_pdma)
    mock_run_action_selection_pdma.assert_called_once()
    # The second argument to run_action_selection_pdma is triaged_inputs dict
    triaged_inputs_as = mock_run_action_selection_pdma.call_args[0][1] 
    thought_arg_as = triaged_inputs_as['original_thought']
    assert thought_arg_as.processing_context is not None
    system_snapshot_as = thought_arg_as.processing_context.get("system_snapshot", {})
    prompt_context_as = format_system_snapshot_for_prompt(system_snapshot_as, thought_arg_as.processing_context)
    assert expected_recent_task_text in prompt_context_as, "ActionSelection PDMA context missing recent tasks header"
    assert completed_task_desc in prompt_context_as, "ActionSelection PDMA context missing completed task description"

    # Clean up tasks from DB
    persistence.delete_tasks_by_ids([completed_task_id, active_task_id])
    # Thoughts are deleted by cascade if source_task_id is FK
    # persistence.delete_thoughts_by_ids([thought_id])

@pytest.mark.asyncio
def test_format_system_snapshot_for_prompt_full_context():
    from ciris_engine.utils.context_formatters import format_system_snapshot_for_prompt, format_user_profiles_for_prompt
    # Mock a full system snapshot and processing context
    system_snapshot = {
        "current_task_details": {"task_id": "t1", "description": "Current Task Desc"},
        "recently_completed_tasks_summary": [
            {"task_id": "c1", "description": "Completed Task 1", "outcome": {"result": "ok"}},
            {"task_id": "c2", "description": "Completed Task 2", "outcome": {"result": "ok2"}},
        ],
        "system_counts": {"pending_tasks": 2},
        "user_profiles": {"alice": {"nick": "Alice", "channel": "general", "interest": "go"}},
    }
    processing_context = {
        "system_snapshot": system_snapshot,
        "other_key": "other_value",
        "initial_task_context": {"irrelevant": True},
    }
    # Format user profiles
    user_profile_str = format_user_profiles_for_prompt(system_snapshot["user_profiles"])
    # Format system snapshot
    snapshot_str = format_system_snapshot_for_prompt(system_snapshot, processing_context)
    # Check user node
    assert "Alice" in user_profile_str
    assert "general" in user_profile_str
    # Check channel node
    assert "Primary Channel: 'general'" in user_profile_str
    # Check tasks and context
    assert "Current Task Context: Current Task Desc" in snapshot_str
    assert "Completed Task 1" in snapshot_str
    assert "Completed Task 2" in snapshot_str
    assert "System State: Pending Tasks=2" in snapshot_str
    # Check other context
    assert "other_key" in snapshot_str
    # Ensure all context is present for DMA
    full_context = user_profile_str + snapshot_str
    assert "Alice" in full_context and "general" in full_context and "Completed Task 1" in full_context
