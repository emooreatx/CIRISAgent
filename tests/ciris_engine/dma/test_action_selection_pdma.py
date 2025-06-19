import pytest
from unittest.mock import MagicMock, AsyncMock
from types import SimpleNamespace
from ciris_engine.registries.base import ServiceRegistry, Priority
from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAEvaluator
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.action_params_v1 import SpeakParams
from ciris_engine.schemas.dma_results_v1 import EthicalDMAResult, CSDMAResult, DSDMAResult
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.foundational_schemas_v1 import SchemaVersion, ThoughtType, ThoughtStatus, ResourceUsage
from ciris_engine.schemas.action_params_v1 import PonderParams
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
    
    # Create dummy response for forced ponder
    dummy_response = ActionSelectionResult(
        selected_action=HandlerActionType.PONDER,
        action_parameters={"questions": ["Forced ponder question 1", "Forced ponder question 2"]},
        rationale="Forced ponder due to initial_task_context",
        confidence=0.8
    )
    
    # Create a mock multi-service sink
    mock_sink = MagicMock()
    async def mock_generate_structured_sync(*args, **kwargs):
        return (
            dummy_response,
            ResourceUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150, cost_usd=0.001)
        )
    mock_sink.generate_structured_sync = mock_generate_structured_sync
    
    evaluator = ActionSelectionPDMAEvaluator(
        service_registry=service_registry,
        model_name="test-model",
        instructor_mode=MagicMock(),
        sink=mock_sink
    )
    triaged_inputs = {
        'original_thought': Thought(thought_id="t1", content="irrelevant", thought_type=ThoughtType.STANDARD, ponder_notes=None, thought_depth=0, context={}, source_task_id="x", status=ThoughtStatus.PENDING, created_at="now", updated_at="now", round_number=1, final_action={}, parent_thought_id=None),
        'ethical_pdma_result': EthicalDMAResult(alignment_check={}, decision="", rationale=None),
        'csdma_result': CSDMAResult.model_construct(plausibility_score=1.0),
        'dsdma_result': DSDMAResult.model_construct(domain="test", score=1.0),
        'current_thought_depth': 0,
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
    # Create proper ActionSelectionResult response
    dummy_llm_response = ActionSelectionResult(
        selected_action=HandlerActionType.SPEAK,
        action_parameters={
            "content": "hi"
        },
        rationale="rationale",
        confidence=0.9
    )
    
    service_registry = ServiceRegistry()
    
    # Create a mock multi-service sink with proper return value
    mock_sink = MagicMock()
    mock_sink.llm = MagicMock()
    async def mock_generate_structured_sync(*args, **kwargs):
        return (
            dummy_llm_response,
            ResourceUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150, cost_usd=0.001)
        )
    mock_sink.llm.generate_structured_sync = mock_generate_structured_sync
    
    evaluator = ActionSelectionPDMAEvaluator(
        service_registry=service_registry,
        model_name="test-model",
        instructor_mode=MagicMock(),
        sink=mock_sink
    )
    
    triaged_inputs = {
        'original_thought': Thought(thought_id="t1", content="hi", thought_type=ThoughtType.STANDARD, ponder_notes=None, thought_depth=0, context={}, source_task_id="x", status=ThoughtStatus.PENDING, created_at="now", updated_at="now", round_number=1, final_action={}, parent_thought_id=None),
        'ethical_pdma_result': EthicalDMAResult(alignment_check={}, decision="", rationale=None),
        'csdma_result': CSDMAResult.model_construct(plausibility_score=1.0),
        'dsdma_result': DSDMAResult.model_construct(domain="test", score=1.0),
        'current_thought_depth': 0,
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
    # Create proper ActionSelectionResult response
    dummy_llm_response = ActionSelectionResult(
        selected_action=HandlerActionType.SPEAK,
        action_parameters={
            "content": "hi"
        },
        rationale="rationale",
        confidence=0.9
    )
    
    service_registry = ServiceRegistry()
    dummy_client = SimpleNamespace(client=MagicMock())
    dummy_service = SimpleNamespace(get_client=lambda: dummy_client)
    service_registry.register_global("llm", dummy_service, priority=Priority.HIGH)
    monkeypatch.setattr("instructor.patch", lambda c, mode: c)
    # Create a mock multi-service sink
    mock_sink = AsyncMock()
    mock_sink.call_llm_structured = AsyncMock(return_value=(
        dummy_llm_response,
        ResourceUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150, cost_usd=0.001)
    ))
    
    evaluator = ActionSelectionPDMAEvaluator(
        service_registry=service_registry,
        model_name="test-model",
        instructor_mode=MagicMock(),
        sink=mock_sink
    )
    class DummyInstrRetry(Exception):
        def errors(self):
            return ["err"]
    dummy_client.client.chat.completions.create = AsyncMock(side_effect=DummyInstrRetry())
    triaged_inputs = {
        'original_thought': Thought(thought_id="t1", content="hi", thought_type=ThoughtType.STANDARD, ponder_notes=None, thought_depth=0, context={}, source_task_id="x", status=ThoughtStatus.PENDING, created_at="now", updated_at="now", round_number=1, final_action={}, parent_thought_id=None),
        'ethical_pdma_result': EthicalDMAResult(alignment_check={}, decision="", rationale=None),
        'csdma_result': CSDMAResult.model_construct(plausibility_score=1.0),
        'dsdma_result': DSDMAResult.model_construct(domain="test", score=1.0),
        'current_thought_depth': 0,
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
    # Create proper ActionSelectionResult response
    dummy_llm_response = ActionSelectionResult(
        selected_action=HandlerActionType.SPEAK,
        action_parameters={
            "content": "hi"
        },
        rationale="rationale",
        confidence=0.9
    )
    
    service_registry = ServiceRegistry()
    dummy_client = SimpleNamespace(client=MagicMock())
    dummy_service = SimpleNamespace(get_client=lambda: dummy_client)
    service_registry.register_global("llm", dummy_service, priority=Priority.HIGH)
    monkeypatch.setattr("instructor.patch", lambda c, mode: c)
    # Create a mock multi-service sink
    mock_sink = AsyncMock()
    mock_sink.call_llm_structured = AsyncMock(return_value=(
        dummy_llm_response,
        ResourceUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150, cost_usd=0.001)
    ))
    
    evaluator = ActionSelectionPDMAEvaluator(
        service_registry=service_registry,
        model_name="test-model",
        instructor_mode=MagicMock(),
        sink=mock_sink
    )
    dummy_client.client.chat.completions.create = AsyncMock(side_effect=Exception("fail"))
    triaged_inputs = {
        'original_thought': Thought(thought_id="t1", content="hi", thought_type=ThoughtType.STANDARD, ponder_notes=None, thought_depth=0, context={}, source_task_id="x", status=ThoughtStatus.PENDING, created_at="now", updated_at="now", round_number=1, final_action={}, parent_thought_id=None),
        'ethical_pdma_result': EthicalDMAResult(alignment_check={}, decision="", rationale=None),
        'csdma_result': CSDMAResult.model_construct(plausibility_score=1.0),
        'dsdma_result': DSDMAResult.model_construct(domain="test", score=1.0),
        'current_thought_depth': 0,
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
