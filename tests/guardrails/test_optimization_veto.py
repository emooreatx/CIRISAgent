import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.guardrails import EthicalGuardrails, OptimizationVetoResult
from ciris_engine.schemas.config_schemas_v1 import GuardrailsConfig
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType

@pytest.mark.asyncio
async def test_optimization_veto_triggers_abort(monkeypatch):
    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=OptimizationVetoResult(
            decision="abort",
            justification="ratio too high",
            entropy_reduction_ratio=12.0,
            affected_values=["autonomy"],
            confidence=0.8,
        )
    )

    guardrails = EthicalGuardrails(mock_client, GuardrailsConfig())
    asp_result = ActionSelectionResult(
        context_summary_for_action_selection="",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.MEMORIZE,
        action_parameters={},
        action_selection_rationale="",
        monitoring_for_selected_action={},
    )

    # Bypass entropy/coherence checks
    monkeypatch.setattr(
        "ciris_engine.guardrails.calculate_epistemic_values",
        AsyncMock(return_value={"entropy": 0.1, "coherence": 0.9}),
    )
    from ciris_engine.guardrails import EpistemicHumilityResult
    monkeypatch.setattr(
        "ciris_engine.guardrails.EthicalGuardrails._evaluate_epistemic_humility",
        AsyncMock(return_value=EpistemicHumilityResult(
            epistemic_certainty="high",
            identified_uncertainties=[],
            reflective_justification="ok",
            recommended_action="proceed",
        ))
    )

    passed, reason, data = await guardrails.check_action_output_safety(asp_result)

    assert not passed
    assert "Optimization veto" in reason
    assert data["optimization_veto"]["decision"] == "abort"

@pytest.mark.asyncio
async def test_optimization_veto_allows_proceed(monkeypatch):
    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=OptimizationVetoResult(
            decision="proceed",
            justification="safe",
            entropy_reduction_ratio=2.0,
            affected_values=[],
            confidence=0.9,
        )
    )

    guardrails = EthicalGuardrails(mock_client, GuardrailsConfig())
    asp_result = ActionSelectionResult(
        context_summary_for_action_selection="",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.SPEAK,
        action_parameters={"content": "hi"},
        action_selection_rationale="",
        monitoring_for_selected_action={},
    )

    monkeypatch.setattr(
        "ciris_engine.guardrails.calculate_epistemic_values",
        AsyncMock(return_value={"entropy": 0.1, "coherence": 0.9}),
    )
    from ciris_engine.guardrails import EpistemicHumilityResult
    monkeypatch.setattr(
        "ciris_engine.guardrails.EthicalGuardrails._evaluate_epistemic_humility",
        AsyncMock(return_value=EpistemicHumilityResult(
            epistemic_certainty="high",
            identified_uncertainties=[],
            reflective_justification="ok",
            recommended_action="proceed",
        ))
    )

    passed, reason, data = await guardrails.check_action_output_safety(asp_result)

    assert passed
    assert data["optimization_veto"]["decision"] == "proceed"
