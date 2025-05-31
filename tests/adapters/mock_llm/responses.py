from types import SimpleNamespace
from typing import Any

from ciris_engine.schemas.dma_results_v1 import (
    EthicalDMAResult,
    CSDMAResult,
    DSDMAResult,
    ActionSelectionResult,
)
from ciris_engine.schemas.feedback_schemas_v1 import (
    OptimizationVetoResult,
    EpistemicHumilityResult,
)
from ciris_engine.schemas.epistemic_schemas_v1 import EntropyResult, CoherenceResult
from ciris_engine.dma.dsdma_base import BaseDSDMA
from ciris_engine.schemas.action_params_v1 import PonderParams
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType


def _attach_extras(obj: Any) -> Any:
    """Mimic instructor extra attributes expected on responses."""
    import json
    # Convert the object to JSON to simulate what a real LLM would return
    try:
        if hasattr(obj, 'model_dump'):
            # Pydantic object
            content_json = json.dumps(obj.model_dump())
        else:
            # Fallback for other objects
            content_json = json.dumps(obj.__dict__ if hasattr(obj, '__dict__') else str(obj))
    except Exception:
        content_json = "{}"
    
    object.__setattr__(obj, "finish_reason", "stop")
    object.__setattr__(obj, "_raw_response", {"mock": True})
    object.__setattr__(obj, "choices", [SimpleNamespace(
        finish_reason="stop",
        message=SimpleNamespace(role="assistant", content=content_json)
    )])
    return obj


def ethical_dma() -> EthicalDMAResult:
    return _attach_extras(
        EthicalDMAResult(alignment_check={"ok": True}, decision="proceed", rationale="mock")
    )


def cs_dma() -> CSDMAResult:
    return _attach_extras(CSDMAResult(plausibility_score=0.9, flags=[]))


def ds_dma() -> DSDMAResult:
    return _attach_extras(DSDMAResult(domain="mock", alignment_score=0.9, flags=[]))


def ds_dma_llm_output() -> BaseDSDMA.LLMOutputForDSDMA:
    result = BaseDSDMA.LLMOutputForDSDMA(
        domain_alignment_score=1.0,
        recommended_action="proceed",
        flags=[],
        reasoning="mock",
    )
    return _attach_extras(result)


def optimization_veto() -> OptimizationVetoResult:
    return _attach_extras(
        OptimizationVetoResult(
            decision="proceed",
            justification="mock",
            entropy_reduction_ratio=0.0,
            affected_values=[],
            confidence=1.0,
        )
    )


def epistemic_humility() -> EpistemicHumilityResult:
    return _attach_extras(
        EpistemicHumilityResult(
            epistemic_certainty="high",
            identified_uncertainties=[],
            reflective_justification="mock",
            recommended_action="proceed",
        )
    )


def action_selection() -> ActionSelectionResult:
    return _attach_extras(
        ActionSelectionResult(
            selected_action=HandlerActionType.PONDER,
            action_parameters=PonderParams(questions=["Mock LLM: What should I do next?"]).model_dump(mode="json"),
            rationale="Mock LLM default action selection.",
            confidence=0.9,
            raw_llm_response="ActionSelectionResult from MockLLM",
        )
    )


def entropy() -> EntropyResult:
    return _attach_extras(EntropyResult(entropy=0.1))


def coherence() -> CoherenceResult:
    return _attach_extras(CoherenceResult(coherence=0.9))


_RESPONSE_MAP = {
    EthicalDMAResult: ethical_dma,
    CSDMAResult: cs_dma,
    DSDMAResult: ds_dma,
    BaseDSDMA.LLMOutputForDSDMA: ds_dma_llm_output,
    OptimizationVetoResult: optimization_veto,
    EpistemicHumilityResult: epistemic_humility,
    ActionSelectionResult: action_selection,
    EntropyResult: entropy,
    CoherenceResult: coherence,
}


def create_response(model: Any) -> Any:
    handler = _RESPONSE_MAP.get(model)
    if handler:
        return handler()
    return _attach_extras(SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="OK"))]))
