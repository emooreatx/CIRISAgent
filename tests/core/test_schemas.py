import pytest
from pydantic import ValidationError
import uuid
from datetime import datetime

# Schemas to test
from ciris_engine.schemas.foundational_schemas_v1 import (
    CIRISSchemaVersion,
    HandlerActionType,
    TaskStatus,
    ThoughtStatus,
    ObservationSourceType,
    DKGAssetType,
    CIRISAgentUAL, CIRISTaskUAL, CIRISKnowledgeAssetUAL, VeilidDID, VeilidRouteID
)
from ciris_engine.schemas.agent_core_schemas_v1 import (
    ObserveParams, SpeakParams, ActParams, PonderParams, RejectParams, DeferParams,
    MemorizeParams, RememberParams, ForgetParams,
    ActionSelectionPDMAResult,
    Task, Thought
)
from ciris_engine.core.agent_processing_queue import ProcessingQueueItem, ProcessingQueue

from ciris_engine.core.observation_schemas import ObservationRecord
from ciris_engine.core.audit_schemas import AuditLogEntry
from ciris_engine.memory.ciris_local_graph import MemoryOpStatus

# --- Tests for foundational_schemas.py ---

def test_enum_values():
    """Test that enums can be accessed and have expected string values."""
    assert CIRISSchemaVersion.V1_0_BETA.value == "1.0-beta"
    assert HandlerActionType.SPEAK.value == "speak"
    assert HandlerActionType.TOOL.value == "tool"
    assert HandlerActionType.TASK_COMPLETE.value == "task_complete"
    assert HandlerActionType.MEMORIZE.value == "memorize"
    assert TaskStatus.PENDING.value == "pending"
    assert TaskStatus.PAUSED.value == "paused" # Test added status
    assert ThoughtStatus.PROCESSING.value == "processing"
    assert ThoughtStatus.PAUSED.value == "paused" # Test added status
    assert ObservationSourceType.USER_REQUEST.value == "user_request"
    assert DKGAssetType.AGENT_PROFILE.value == "AgentProfile"

def test_enum_case_insensitive():
    """Enums should accept case-insensitive inputs."""
    assert HandlerActionType("MEMORIZE") is HandlerActionType.MEMORIZE
    assert TaskStatus("PENDING") is TaskStatus.PENDING
    assert MemoryOpStatus("OK") is MemoryOpStatus.OK

def test_ual_did_types():
    """Test that UAL/DID types are essentially strings."""
    agent_ual: CIRISAgentUAL = "did:example:agent1"
    task_ual: CIRISTaskUAL = "ual:task:abc"
    ka_ual: CIRISKnowledgeAssetUAL = "ual:ka:xyz"
    veilid_did: VeilidDID = "did:key:zExampleKey"
    veilid_route: VeilidRouteID = "route_id_example"
    assert isinstance(agent_ual, str)
    assert isinstance(task_ual, str)
    assert isinstance(ka_ual, str)
    assert isinstance(veilid_did, str)
    assert isinstance(veilid_route, str)

# --- Tests for agent_core_schemas.py ---

def test_task_instantiation_and_defaults():
    task_desc = "Test task description"
    task = Task(description=task_desc, task_id="task_123", created_at=datetime.utcnow().isoformat(), updated_at=datetime.utcnow().isoformat())
    assert task.description == task_desc
    assert task.task_id == "task_123"
    assert task.status == TaskStatus.PENDING # Default
    assert task.priority == 0 # Default
    assert task.due_date is None # Added field, default None
    assert task.parent_goal_id is None # Added field, default None
    assert isinstance(task.created_at, str)
    assert isinstance(task.updated_at, str)

def test_thought_instantiation_and_defaults():
    thought_content = "Test thought content"
    thought = Thought(
        source_task_id="task_123",
        content=thought_content,
        thought_id="thought_abc",
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
        round_created=1 # Added field
    )
    assert thought.content == thought_content
    assert thought.thought_id == "thought_abc"
    assert thought.status == ThoughtStatus.PENDING # Default
    assert thought.priority == 0 # Added field, default 0
    assert thought.round_created == 1 # Added field
    assert thought.action_count == 0
    assert thought.history == []
    assert thought.escalations == []
    assert thought.is_terminal is False
    assert thought.round_processed is None # Added field, default None
    assert thought.depth == 0 # Default
    assert thought.ponder_count == 0 # Default

def test_action_selection_pdma_result_instantiation():
    # Basic instantiation check with all required fields
    result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="Test context summary",
        action_alignment_check={"speak": "aligned", "ponder": "neutral"},
        selected_handler_action=HandlerActionType.SPEAK,
        action_parameters=SpeakParams(content="Hello world"),
        action_selection_rationale="Speaking is the best option here.",
        monitoring_for_selected_action="Monitor user response.",
        confidence_score=0.9,
        # Optional fields can be omitted or set to None
        action_conflicts=None,
        action_resolution=None,
        raw_llm_response="Raw LLM output string",
        ethical_assessment_summary={"status": "pass"},
        csdma_assessment_summary={"score": 0.9},
        dsdma_assessment_summary={"score": 0.8}
    )
    assert result.selected_handler_action == HandlerActionType.SPEAK
    assert isinstance(result.action_parameters, SpeakParams)
    assert result.action_parameters.content == "Hello world"
    assert result.context_summary_for_action_selection == "Test context summary"
    assert result.action_selection_rationale == "Speaking is the best option here."

def test_audit_log_entry_instantiation():
    entry = AuditLogEntry(
        event_id=str(uuid.uuid4()),
        event_timestamp=datetime.utcnow().isoformat(),
        event_type="TestEvent",
        originator_id="agent:test_agent",
        event_summary="A test event occurred."
    )
    assert entry.event_type == "TestEvent"
    assert entry.schema_version == CIRISSchemaVersion.V1_0_BETA

# --- Tests for agent_processing_queue.py ---

def test_processing_queue_item_instantiation():
    item = ProcessingQueueItem(
        thought_id="thought_xyz",
        source_task_id="task_123",
        thought_type="seed_task_thought",
        content="Queue item content",
        priority=5
    )
    assert item.thought_id == "thought_xyz"
    assert item.priority == 5
    assert item.initial_context == {} # Default factory

def test_processing_queue_item_from_thought():
    now_iso = datetime.utcnow().isoformat()
    thought_instance = Thought(
        thought_id="thought_efg",
        source_task_id="task_456",
        thought_type="ponder_thought",
        content="Original thought content for queue",
        priority=3,
        status=ThoughtStatus.PENDING,
        created_at=now_iso,
        updated_at=now_iso,
        round_created=2,
        processing_context={"key": "value"},
        ponder_notes=["question1"]
    )

    queue_item = ProcessingQueueItem.from_thought(thought_instance)
    
    assert queue_item.thought_id == thought_instance.thought_id
    assert queue_item.source_task_id == thought_instance.source_task_id
    assert queue_item.thought_type == thought_instance.thought_type
    assert queue_item.content == thought_instance.content
    assert queue_item.priority == thought_instance.priority
    assert queue_item.initial_context == thought_instance.processing_context
    assert queue_item.ponder_notes == thought_instance.ponder_notes
    assert queue_item.raw_input_string == str(thought_instance.content)

def test_processing_queue_item_from_thought_with_overrides():
    now_iso = datetime.utcnow().isoformat()
    thought_instance = Thought(
        thought_id="thought_hij",
        source_task_id="task_789",
        content="Original",
        priority=1,
        created_at=now_iso, updated_at=now_iso, round_created=1
    )
    
    custom_content = {"detail": "richer content for queue"}
    custom_raw_input = "User said something specific"
    custom_initial_ctx = {"source": "direct_input"}

    queue_item = ProcessingQueueItem.from_thought(
        thought_instance,
        raw_input=custom_raw_input,
        initial_ctx=custom_initial_ctx,
        queue_item_content=custom_content
    )
    assert queue_item.content == custom_content
    assert queue_item.raw_input_string == custom_raw_input
    assert queue_item.initial_context == custom_initial_ctx

def test_processing_queue_type_alias():
    """Test that ProcessingQueue is a deque of ProcessingQueueItem."""
    import collections
    queue: ProcessingQueue = collections.deque()
    item = ProcessingQueueItem(
        thought_id="q_item_1", source_task_id="t_1", thought_type="t", content="c", priority=0
    )
    queue.append(item)
    assert isinstance(queue, collections.deque)
    assert isinstance(queue[0], ProcessingQueueItem)

# Example of a validation test if a field had specific constraints
def test_memorize_params_confidence_validation():
    with pytest.raises(ValidationError):
        MemorizeParams(knowledge_unit_description="test", knowledge_data="data", knowledge_type="fact", source="test", confidence=1.5) # Confidence > 1.0
    with pytest.raises(ValidationError):
        MemorizeParams(knowledge_unit_description="test", knowledge_data="data", knowledge_type="fact", source="test", confidence=-0.5) # Confidence < 0.0
    
    # Valid
    params = MemorizeParams(knowledge_unit_description="test", knowledge_data="data", knowledge_type="fact", source="test", confidence=0.5)
    assert params.confidence == 0.5
