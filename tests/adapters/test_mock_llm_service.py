import pytest

from ciris_engine.logic.dma.dsdma_base import BaseDSDMA
from ciris_engine.schemas.conscience.core import (
    CoherenceCheckResult,
    EntropyCheckResult,
    EpistemicHumilityResult,
    OptimizationVetoResult,
)
from ciris_engine.schemas.dma.results import ActionSelectionDMAResult, CSDMAResult, EthicalDMAResult
from tests.adapters.mock_llm import MockLLMClient


@pytest.mark.asyncio
async def test_mock_llm_structured_outputs():
    client = MockLLMClient()
    assert isinstance(await client._create(response_model=EthicalDMAResult), EthicalDMAResult)
    assert isinstance(await client._create(response_model=CSDMAResult), CSDMAResult)
    dsdma = await client._create(response_model=BaseDSDMA.LLMOutputForDSDMA)
    assert isinstance(dsdma, BaseDSDMA.LLMOutputForDSDMA)
    assert hasattr(dsdma, "finish_reason")
    assert isinstance(await client._create(response_model=ActionSelectionDMAResult), ActionSelectionDMAResult)
    assert isinstance(await client._create(response_model=OptimizationVetoResult), OptimizationVetoResult)
    assert isinstance(await client._create(response_model=EpistemicHumilityResult), EpistemicHumilityResult)
    assert isinstance(await client._create(response_model=EntropyCheckResult), EntropyCheckResult)
    assert isinstance(await client._create(response_model=CoherenceCheckResult), CoherenceCheckResult)
