from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from ciris_engine.adapters.base import Service
from ciris_engine.schemas.dma_results_v1 import (
    EthicalDMAResult,
    CSDMAResult,
    DSDMAResult,
    ActionSelectionResult,
)
from ciris_engine.schemas.action_params_v1 import PonderParams # Added import
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType # Added import
from ciris_engine.schemas.feedback_schemas_v1 import (
    OptimizationVetoResult,
    EpistemicHumilityResult,
)
from ciris_engine.dma.dsdma_base import BaseDSDMA
from ciris_engine.schemas.epistemic_schemas_v1 import (
    EntropyResult,
    CoherenceResult,
)


class MockLLMClient:
    """Lightweight stand-in for an OpenAI-compatible client."""

    def __init__(self) -> None:
        self.model_name = "mock-model"
        self.client = self
        self.instruct_client = self
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, *_, response_model=None, **__) -> Any:  # noqa: D401
        if response_model is EthicalDMAResult:
            return EthicalDMAResult(
                alignment_check={"ok": True},
                decision="proceed",
                rationale="mock",
            )
        if response_model is CSDMAResult:
            return CSDMAResult(plausibility_score=0.9, flags=[])
        if response_model is DSDMAResult:
            return DSDMAResult(domain="mock", alignment_score=0.9, flags=[])
        if response_model is BaseDSDMA.LLMOutputForDSDMA:
            result = BaseDSDMA.LLMOutputForDSDMA(
                domain_alignment_score=1.0,
                recommended_action="proceed",
                flags=[],
                reasoning="mock",
            )
            # Mimic instructor's extra attributes
            object.__setattr__(result, "finish_reason", "stop")
            object.__setattr__(result, "_raw_response", {"mock": True})
            return result
        if response_model is OptimizationVetoResult:
            return OptimizationVetoResult(
                decision="proceed",
                justification="mock",
                entropy_reduction_ratio=0.0,
                affected_values=[],
                confidence=1.0,
            )
        if response_model is EpistemicHumilityResult:
            return EpistemicHumilityResult(
                epistemic_certainty="high",
                identified_uncertainties=[],
                reflective_justification="mock",
                recommended_action="proceed",
            )
        if response_model is ActionSelectionResult:
            # Return a default PONDER action for mock mode
            return ActionSelectionResult(
                selected_action=HandlerActionType.PONDER,
                action_parameters=PonderParams(questions=["Mock LLM: What should I do next?"]).model_dump(mode='json'),
                rationale="Mock LLM default action selection.",
                confidence=0.9,
                raw_llm_response="ActionSelectionResult from MockLLM"
            )
        if response_model is EntropyResult:
            return EntropyResult(entropy=0.1)
        if response_model is CoherenceResult:
            return CoherenceResult(coherence=0.9)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="OK"))])


class MockLLMService(Service):
    """Mock LLM service used for offline testing."""

    def __init__(self, *_, **__) -> None:
        super().__init__()
        self._client: Optional[MockLLMClient] = None

    async def start(self) -> None:
        await super().start()
        self._client = MockLLMClient()

    async def stop(self) -> None:
        self._client = None
        await super().stop()

    def get_client(self) -> MockLLMClient:
        if not self._client:
            raise RuntimeError("MockLLMService has not been started")
        return self._client
