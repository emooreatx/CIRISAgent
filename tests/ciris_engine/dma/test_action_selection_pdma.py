import pytest
from unittest.mock import MagicMock, AsyncMock
from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAEvaluator, HandlerActionType, ActionSelectionResult, PonderParams, SpeakParams
from ciris_engine.schemas.dma_results_v1 import EthicalDMAResult, CSDMAResult, DSDMAResult
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.foundational_schemas_v1 import CIRISSchemaVersion
from ciris_engine.schemas.action_params_v1 import PonderParams, SpeakParams
from pydantic import ValidationError

class DummyLLMResponse:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self._raw_response = "RAW"

@pytest.mark.asyncio
async def test_forced_ponder(monkeypatch):
    evaluator = ActionSelectionPDMAEvaluator(
        aclient=MagicMock(),
        model_name="test-model",
        instructor_mode=MagicMock()
    )
    triaged_inputs = {
        'original_thought': Thought(thought_id="t1", content="irrelevant", thought_type="test", ponder_notes=None, ponder_count=0, context={}, source_task_id="x", status="PENDING", created_at="now", updated_at="now", round_number=1, final_action={}, parent_thought_id=None),
        'ethical_pdma_result': EthicalDMAResult(alignment_check={}, decision="", rationale=None),
        'csdma_result': CSDMAResult.model_construct(plausibility_score=1.0),
        'dsdma_result': DSDMAResult.model_construct(domain="test", alignment_score=1.0),
        'current_ponder_count': 0,
        'max_ponder_rounds': 3,
        'processing_context': {'initial_task_context': {'content': 'ponder'}}
    }
    result = await evaluator.evaluate(triaged_inputs)
    assert isinstance(result, ActionSelectionResult)
    assert result.selected_action == HandlerActionType.PONDER
    assert "Forced" in result.rationale
    # Schema-driven assertion
    ponder_params = PonderParams(**result.action_parameters)
    assert isinstance(ponder_params.questions, list)
    assert any("Forced" in q for q in ponder_params.questions)

@pytest.mark.asyncio
async def test_llm_success(monkeypatch):
    # Patch the instructor client to return a dummy LLM response
    dummy_llm_response = DummyLLMResponse(
        schema_version=CIRISSchemaVersion.V1_0_BETA,
        context_summary_for_action_selection="summary",
        action_alignment_check={"SPEAK": "ok"},
        action_conflicts=None,
        action_resolution=None,
        selected_action=HandlerActionType.SPEAK,
        action_parameters={"content": "hi"},
        action_selection_rationale="rationale",
        monitoring_for_selected_action="monitor",
        confidence_score=0.9
    )
    evaluator = ActionSelectionPDMAEvaluator(
        aclient=MagicMock(),
        model_name="test-model",
        instructor_mode=MagicMock()
    )
    evaluator.aclient.chat.completions.create = AsyncMock(return_value=dummy_llm_response)
    triaged_inputs = {
        'original_thought': Thought(thought_id="t1", content="hi", thought_type="test", ponder_notes=None, ponder_count=0, context={}, source_task_id="x", status="PENDING", created_at="now", updated_at="now", round_number=1, final_action={}, parent_thought_id=None),
        'ethical_pdma_result': EthicalDMAResult(alignment_check={}, decision="", rationale=None),
        'csdma_result': CSDMAResult.model_construct(plausibility_score=1.0),
        'dsdma_result': DSDMAResult.model_construct(domain="test", alignment_score=1.0),
        'current_ponder_count': 0,
        'max_ponder_rounds': 3,
        'processing_context': {}
    }
    result = await evaluator.evaluate(triaged_inputs)
    assert isinstance(result, ActionSelectionResult)
    assert result.selected_action == HandlerActionType.SPEAK
    # Schema-driven assertion
    speak_params = SpeakParams(**result.action_parameters)
    assert speak_params.content == "hi"
    assert result.confidence == 0.9

@pytest.mark.asyncio
async def test_instructor_retry(monkeypatch):
    evaluator = ActionSelectionPDMAEvaluator(
        aclient=MagicMock(),
        model_name="test-model",
        instructor_mode=MagicMock()
    )
    class DummyInstrRetry(Exception):
        def errors(self):
            return ["err"]
    evaluator.aclient.chat.completions.create = AsyncMock(side_effect=DummyInstrRetry())
    triaged_inputs = {
        'original_thought': Thought(thought_id="t1", content="hi", thought_type="test", ponder_notes=None, ponder_count=0, context={}, source_task_id="x", status="PENDING", created_at="now", updated_at="now", round_number=1, final_action={}, parent_thought_id=None),
        'ethical_pdma_result': EthicalDMAResult(alignment_check={}, decision="", rationale=None),
        'csdma_result': CSDMAResult.model_construct(plausibility_score=1.0),
        'dsdma_result': DSDMAResult.model_construct(domain="test", alignment_score=1.0),
        'current_ponder_count': 0,
        'max_ponder_rounds': 3,
        'processing_context': {}
    }
    result = await evaluator.evaluate(triaged_inputs)
    assert result.selected_action == HandlerActionType.PONDER
    assert "InstructorRetryException" in result.rationale or "Fallback" in result.rationale
    # Schema-driven assertion
    ponder_params = PonderParams(**result.action_parameters)
    assert any("System error" in q or "err" in q for q in ponder_params.questions)

@pytest.mark.asyncio
async def test_general_exception(monkeypatch):
    evaluator = ActionSelectionPDMAEvaluator(
        aclient=MagicMock(),
        model_name="test-model",
        instructor_mode=MagicMock()
    )
    evaluator.aclient.chat.completions.create = AsyncMock(side_effect=Exception("fail"))
    triaged_inputs = {
        'original_thought': Thought(thought_id="t1", content="hi", thought_type="test", ponder_notes=None, ponder_count=0, context={}, source_task_id="x", status="PENDING", created_at="now", updated_at="now", round_number=1, final_action={}, parent_thought_id=None),
        'ethical_pdma_result': EthicalDMAResult(alignment_check={}, decision="", rationale=None),
        'csdma_result': CSDMAResult.model_construct(plausibility_score=1.0),
        'dsdma_result': DSDMAResult.model_construct(domain="test", alignment_score=1.0),
        'current_ponder_count': 0,
        'max_ponder_rounds': 3,
        'processing_context': {}
    }
    result = await evaluator.evaluate(triaged_inputs)
    assert result.selected_action == HandlerActionType.PONDER
    assert "General Exception" in result.rationale or "Fallback" in result.rationale
    # Schema-driven assertion
    ponder_params = PonderParams(**result.action_parameters)
    assert any("System error" in q or "fail" in q for q in ponder_params.questions)

# Optionally, add a negative test to ensure invalid action_parameters raise ValidationError
@pytest.mark.asyncio
async def test_invalid_action_parameters_schema():
    # Simulate a result with invalid action_parameters for SPEAK
    invalid_action_parameters = {"not_content": "nope"}
    with pytest.raises(ValidationError):
        SpeakParams(**invalid_action_parameters)
