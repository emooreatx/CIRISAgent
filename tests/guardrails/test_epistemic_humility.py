import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.guardrails import (
    EthicalGuardrails,
    EpistemicHumilityResult,
)
from ciris_engine.core.config_schemas import GuardrailsConfig
from ciris_engine.core.dma_results import ActionSelectionPDMAResult
from ciris_engine.core.foundational_schemas import HandlerActionType


@pytest.mark.asyncio
async def test_humility_defer(monkeypatch):
    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=EpistemicHumilityResult(
            epistemic_certainty="low",
            identified_uncertainties=["u"],
            reflective_justification="unknown",
            recommended_action="defer",
        )
    )

    guardrails = EthicalGuardrails(mock_client, GuardrailsConfig())
    asp_result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.MEMORIZE,
        action_parameters={},
        action_selection_rationale="",
        monitoring_for_selected_action={},
    )

    monkeypatch.setattr(
        "ciris_engine.guardrails.calculate_epistemic_values",
        AsyncMock(return_value={"entropy": 0.1, "coherence": 0.9}),
    )
    from ciris_engine.guardrails import OptimizationVetoResult
    monkeypatch.setattr(
        "ciris_engine.guardrails.EthicalGuardrails._evaluate_optimization_veto",
        AsyncMock(return_value=OptimizationVetoResult(
            decision="proceed",
            justification="ok",
            entropy_reduction_ratio=1.0,
            affected_values=[],
            confidence=0.9,
        ))
    )

    passed, reason, data = await guardrails.check_action_output_safety(asp_result)

    assert not passed
    assert "humility" in reason.lower()
    assert data["epistemic_humility"]["recommended_action"] == "defer"


@pytest.mark.asyncio
async def test_humility_proceed(monkeypatch):
    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=EpistemicHumilityResult(
            epistemic_certainty="high",
            identified_uncertainties=[],
            reflective_justification="ok",
            recommended_action="proceed",
        )
    )

    guardrails = EthicalGuardrails(mock_client, GuardrailsConfig())
    asp_result = ActionSelectionPDMAResult(
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
    from ciris_engine.guardrails import OptimizationVetoResult
    monkeypatch.setattr(
        "ciris_engine.guardrails.EthicalGuardrails._evaluate_optimization_veto",
        AsyncMock(return_value=OptimizationVetoResult(
            decision="proceed",
            justification="ok",
            entropy_reduction_ratio=1.0,
            affected_values=[],
            confidence=0.9,
        ))
    )

    passed, reason, data = await guardrails.check_action_output_safety(asp_result)

    assert passed
    assert data["epistemic_humility"]["recommended_action"] == "proceed"
