import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.faculties import epistemic
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.faculty_schemas_v1 import EntropyResult, CoherenceResult
from ciris_engine.schemas.feedback_schemas_v1 import OptimizationVetoResult, EpistemicHumilityResult


@pytest.mark.asyncio
async def test_calculate_epistemic_values_success():
    sink = MagicMock()
    # Mock generate_structured_sync to return the expected results
    sink.generate_structured_sync = AsyncMock(side_effect=[
        (EntropyResult(entropy=0.25, faculty_name="entropy"), None),  # First call for entropy
        (CoherenceResult(coherence=0.85, faculty_name="coherence"), None)  # Second call for coherence
    ])
    result = await epistemic.calculate_epistemic_values("hello", sink)
    assert result["entropy"] == 0.25
    assert result["coherence"] == 0.85
    assert "error" not in result


@pytest.mark.asyncio
async def test_evaluate_optimization_veto_returns_schema():
    sink = MagicMock()
    mock_result = OptimizationVetoResult(
        decision="proceed",
        justification="ok",
        entropy_reduction_ratio=0.1,
        affected_values=[],
        confidence=0.9,
    )
    sink.generate_structured_sync = AsyncMock(return_value=(mock_result, None))
    action = ActionSelectionResult(
        selected_action=HandlerActionType.SPEAK,
        action_parameters={"content": "hi"},
        rationale="r",
    )
    result = await epistemic.evaluate_optimization_veto(action, sink)
    assert isinstance(result, OptimizationVetoResult)
    assert result.decision == "proceed"


@pytest.mark.asyncio
async def test_evaluate_epistemic_humility_returns_schema():
    sink = MagicMock()
    mock_result = EpistemicHumilityResult(
        epistemic_certainty=0.8,
        identified_uncertainties=[],
        reflective_justification="none",
        recommended_action="proceed",
    )
    sink.generate_structured_sync = AsyncMock(return_value=(mock_result, None))
    action = ActionSelectionResult(
        selected_action=HandlerActionType.SPEAK,
        action_parameters={"content": "hi"},
        rationale="r",
    )
    result = await epistemic.evaluate_epistemic_humility(action, sink)
    assert isinstance(result, EpistemicHumilityResult)
    assert result.recommended_action == "proceed"
