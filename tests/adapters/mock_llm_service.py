from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from ciris_engine.adapters.base import Service
from ciris_engine.schemas.dma_results_v1 import (
    EthicalDMAResult,
    CSDMAResult,
    DSDMAResult,
)
from ciris_engine.schemas.feedback_schemas_v1 import (
    OptimizationVetoResult,
    EpistemicHumilityResult,
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
