import pytest
from unittest.mock import MagicMock, AsyncMock
from types import SimpleNamespace
from ciris_engine.registries.base import ServiceRegistry, Priority
from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAEvaluator, HandlerActionType, ActionSelectionResult, PonderParams, SpeakParams
from ciris_engine.schemas.dma_results_v1 import EthicalDMAResult, CSDMAResult, DSDMAResult
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.foundational_schemas_v1 import SchemaVersion, ThoughtType, ThoughtStatus
from ciris_engine.schemas.action_params_v1 import PonderParams, SpeakParams
from pydantic import ValidationError

class DummyLLMResponse:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self._raw_response = "RAW"

@pytest.mark.asyncio
async def test_forced_ponder(monkeypatch):
    service_registry = ServiceRegistry()
    # Create a mock client structure that matches what the ActionSelectionPDMA expects
    mock_chat_completions = AsyncMock()
    mock_chat_completions.create = AsyncMock()
    
    # Create the actual client mock that instructor.patch will work with
    mock_client = MagicMock()
    mock_client.chat = SimpleNamespace(completions=mock_chat_completions)
    
    dummy_client = SimpleNamespace(client=mock_client)
    dummy_service = SimpleNamespace(get_client=lambda: dummy_client)
    service_registry.register_global("llm", dummy_service, priority=Priority.HIGH)
    monkeypatch.setattr("instructor.patch", lambda c, mode: c)
    evaluator = ActionSelectionPDMAEvaluator(
        service_registry=service_registry,
        model_name="test-model",
        instructor_mode=MagicMock(),
    )
    triaged_inputs = {
        'original_thought': Thought(thought_id="t1", content="irrelevant", thought_type=ThoughtType.STANDARD, ponder_notes=None, ponder_count=0, context={}, source_task_id="x", status=ThoughtStatus.PENDING, created_at="now", updated_at="now", round_number=1, final_action={}, parent_thought_id=None),
        'ethical_pdma_result': EthicalDMAResult(alignment_check={}, decision="", rationale=None),
        'csdma_result': CSDMAResult.model_construct(plausibility_score=1.0),
        'dsdma_result': DSDMAResult.model_construct(domain="test", score=1.0),
        'current_ponder_count': 0,
        'max_rounds': 3,
        'processing_context': SimpleNamespace(initial_task_context=SimpleNamespace(content='ponder'))
    }
    result = await evaluator.evaluate(triaged_inputs)
    assert isinstance(result, ActionSelectionResult)
    assert result.selected_action == HandlerActionType.PONDER
    assert "Forced" in result.rationale
    # Schema-driven assertion
    if isinstance(result.action_parameters, PonderParams):
        ponder_params = result.action_parameters
    else:
        ponder_params = PonderParams(**result.action_parameters)
    assert isinstance(ponder_params.questions, list)
    assert any("Forced" in q for q in ponder_params.questions)

@pytest.mark.asyncio
async def test_llm_success(monkeypatch):
    # Patch the instructor client to return a dummy LLM response
    from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope
    dummy_llm_response = DummyLLMResponse(
        schema_version=SchemaVersion.V1_0,
        context_summary_for_action_selection="summary",
        action_alignment_check={"SPEAK": "ok"},
        action_conflicts=None,
        action_resolution=None,
        selected_action=HandlerActionType.SPEAK,
        action_parameters={
            # Provide a valid GraphNode for content
            "content": GraphNode(
                id=NodeType.CONCEPT,
                type=NodeType.CONCEPT,
                scope=GraphScope.LOCAL,
                attributes={"content": "hi"},
                version=NodeType.CONCEPT  # Use a valid NodeType for version
            )
        },
        action_selection_rationale="rationale",
        rationale="rationale",  # Add rationale attribute for compatibility
        monitoring_for_selected_action="monitor",
        confidence_score=0.9,
        confidence=0.9  # Add confidence attribute for compatibility
    )
    service_registry = ServiceRegistry()
    dummy_client = SimpleNamespace(client=MagicMock())
    dummy_service = SimpleNamespace(get_client=lambda: dummy_client)
    service_registry.register_global("llm", dummy_service, priority=Priority.HIGH)
    monkeypatch.setattr("instructor.patch", lambda c, mode: c)
    evaluator = ActionSelectionPDMAEvaluator(
        service_registry=service_registry,
        model_name="test-model",
        instructor_mode=MagicMock()
    )
    dummy_client.client.chat.completions.create = AsyncMock(return_value=dummy_llm_response)
    triaged_inputs = {
        'original_thought': Thought(thought_id="t1", content="hi", thought_type=ThoughtType.STANDARD, ponder_notes=None, ponder_count=0, context={}, source_task_id="x", status=ThoughtStatus.PENDING, created_at="now", updated_at="now", round_number=1, final_action={}, parent_thought_id=None),
        'ethical_pdma_result': EthicalDMAResult(alignment_check={}, decision="", rationale=None),
        'csdma_result': CSDMAResult.model_construct(plausibility_score=1.0),
        'dsdma_result': DSDMAResult.model_construct(domain="test", score=1.0),
        'current_ponder_count': 0,
        'max_rounds': 3,
        'processing_context': {}
    }
    result = await evaluator.evaluate(triaged_inputs)
    assert isinstance(result, ActionSelectionResult)
    assert result.selected_action == HandlerActionType.SPEAK
    # Schema-driven assertion
    if isinstance(result.action_parameters, SpeakParams):
        speak_params = result.action_parameters
    else:
        speak_params = SpeakParams(**result.action_parameters)
    # Patch: GraphNode now used for content, check attributes["content"]
    if hasattr(speak_params.content, "attributes"):
        assert speak_params.content.attributes["content"] == "hi"
    else:
        assert speak_params.content == "hi"
    assert result.confidence == 0.9

@pytest.mark.asyncio
async def test_instructor_retry(monkeypatch):
    service_registry = ServiceRegistry()
    dummy_client = SimpleNamespace(client=MagicMock())
    dummy_service = SimpleNamespace(get_client=lambda: dummy_client)
    service_registry.register_global("llm", dummy_service, priority=Priority.HIGH)
    monkeypatch.setattr("instructor.patch", lambda c, mode: c)
    evaluator = ActionSelectionPDMAEvaluator(
        service_registry=service_registry,
        model_name="test-model",
        instructor_mode=MagicMock()
    )
    class DummyInstrRetry(Exception):
        def errors(self):
            return ["err"]
    dummy_client.client.chat.completions.create = AsyncMock(side_effect=DummyInstrRetry())
    triaged_inputs = {
        'original_thought': Thought(thought_id="t1", content="hi", thought_type=ThoughtType.STANDARD, ponder_notes=None, ponder_count=0, context={}, source_task_id="x", status=ThoughtStatus.PENDING, created_at="now", updated_at="now", round_number=1, final_action={}, parent_thought_id=None),
        'ethical_pdma_result': EthicalDMAResult(alignment_check={}, decision="", rationale=None),
        'csdma_result': CSDMAResult.model_construct(plausibility_score=1.0),
        'dsdma_result': DSDMAResult.model_construct(domain="test", score=1.0),
        'current_ponder_count': 0,
        'max_rounds': 3,
        'processing_context': {}
    }
    result = await evaluator.evaluate(triaged_inputs)
    assert result.selected_action == HandlerActionType.PONDER
    assert "InstructorRetryException" in result.rationale or "Fallback" in result.rationale
    # Schema-driven assertion
    if isinstance(result.action_parameters, PonderParams):
        ponder_params = result.action_parameters
    else:
        ponder_params = PonderParams(**result.action_parameters)
    assert any("System error" in q or "err" in q for q in ponder_params.questions)

@pytest.mark.asyncio
async def test_general_exception(monkeypatch):
    service_registry = ServiceRegistry()
    dummy_client = SimpleNamespace(client=MagicMock())
    dummy_service = SimpleNamespace(get_client=lambda: dummy_client)
    service_registry.register_global("llm", dummy_service, priority=Priority.HIGH)
    monkeypatch.setattr("instructor.patch", lambda c, mode: c)
    evaluator = ActionSelectionPDMAEvaluator(
        service_registry=service_registry,
        model_name="test-model",
        instructor_mode=MagicMock()
    )
    dummy_client.client.chat.completions.create = AsyncMock(side_effect=Exception("fail"))
    triaged_inputs = {
        'original_thought': Thought(thought_id="t1", content="hi", thought_type=ThoughtType.STANDARD, ponder_notes=None, ponder_count=0, context={}, source_task_id="x", status=ThoughtStatus.PENDING, created_at="now", updated_at="now", round_number=1, final_action={}, parent_thought_id=None),
        'ethical_pdma_result': EthicalDMAResult(alignment_check={}, decision="", rationale=None),
        'csdma_result': CSDMAResult.model_construct(plausibility_score=1.0),
        'dsdma_result': DSDMAResult.model_construct(domain="test", score=1.0),
        'current_ponder_count': 0,
        'max_rounds': 3,
        'processing_context': {}
    }
    result = await evaluator.evaluate(triaged_inputs)
    assert result.selected_action == HandlerActionType.PONDER
    assert "General Exception" in result.rationale or "Fallback" in result.rationale
    # Schema-driven assertion
    if isinstance(result.action_parameters, PonderParams):
        ponder_params = result.action_parameters
    else:
        ponder_params = PonderParams(**result.action_parameters)
    assert any("System error" in q or "fail" in q for q in ponder_params.questions)

# Optionally, add a negative test to ensure invalid action_parameters raise ValidationError
@pytest.mark.asyncio
async def test_invalid_action_parameters_schema():
    # Simulate a result with invalid action_parameters for SPEAK
    invalid_action_parameters = {"not_content": "nope"}
    with pytest.raises(ValidationError):
        SpeakParams(**invalid_action_parameters)
