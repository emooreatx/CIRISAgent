import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.faculties import epistemic
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.epistemic_schemas_v1 import EntropyResult, CoherenceResult
from ciris_engine.schemas.feedback_schemas_v1 import OptimizationVetoResult, EpistemicHumilityResult


@pytest.mark.asyncio
async def test_calculate_epistemic_values_success():
    aclient = MagicMock()
    # First call returns entropy, second call returns coherence
    aclient.chat.completions.create = AsyncMock(side_effect=[
        EntropyResult(entropy=0.25),
        CoherenceResult(coherence=0.85)
    ])
    result = await epistemic.calculate_epistemic_values("hello", aclient)
    assert result["entropy"] == 0.25
    assert result["coherence"] == 0.85
    assert "error" not in result


@pytest.mark.asyncio
async def test_evaluate_optimization_veto_returns_schema():
    aclient = MagicMock()
    mock_result = OptimizationVetoResult(
        decision="proceed",
        justification="ok",
        entropy_reduction_ratio=0.1,
        affected_values=[],
        confidence=0.9,
    )
    aclient.chat.completions.create = AsyncMock(return_value=mock_result)
    action = ActionSelectionResult(
        selected_action=HandlerActionType.SPEAK,
        action_parameters={"content": "hi"},
        rationale="r",
    )
    result = await epistemic.evaluate_optimization_veto(action, aclient)
    assert isinstance(result, OptimizationVetoResult)
    assert result.decision == "proceed"


@pytest.mark.asyncio
async def test_evaluate_epistemic_humility_returns_schema():
    aclient = MagicMock()
    mock_result = EpistemicHumilityResult(
        epistemic_certainty=0.8,
        identified_uncertainties=[],
        reflective_justification="none",
        recommended_action="proceed",
    )
    aclient.chat.completions.create = AsyncMock(return_value=mock_result)
    action = ActionSelectionResult(
        selected_action=HandlerActionType.SPEAK,
        action_parameters={"content": "hi"},
        rationale="r",
    )
    result = await epistemic.evaluate_epistemic_humility(action, aclient)
    assert isinstance(result, EpistemicHumilityResult)
    assert result.recommended_action == "proceed"
