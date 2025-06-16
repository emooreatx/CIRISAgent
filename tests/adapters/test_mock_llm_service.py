import pytest
from tests.adapters.mock_llm import MockLLMClient
from ciris_engine.schemas.dma_results_v1 import EthicalDMAResult, CSDMAResult, ActionSelectionResult
from ciris_engine.schemas.feedback_schemas_v1 import OptimizationVetoResult, EpistemicHumilityResult
from ciris_engine.dma.dsdma_base import BaseDSDMA
from ciris_engine.schemas.faculty_schemas_v1 import EntropyResult, CoherenceResult

@pytest.mark.asyncio
async def test_mock_llm_structured_outputs():
    client = MockLLMClient()
    assert isinstance(await client._create(response_model=EthicalDMAResult), EthicalDMAResult)
    assert isinstance(await client._create(response_model=CSDMAResult), CSDMAResult)
    dsdma = await client._create(response_model=BaseDSDMA.LLMOutputForDSDMA)
    assert isinstance(dsdma, BaseDSDMA.LLMOutputForDSDMA)
    assert hasattr(dsdma, "finish_reason")
    assert isinstance(await client._create(response_model=ActionSelectionResult), ActionSelectionResult)
    assert isinstance(await client._create(response_model=OptimizationVetoResult), OptimizationVetoResult)
    assert isinstance(await client._create(response_model=EpistemicHumilityResult), EpistemicHumilityResult)
    assert isinstance(await client._create(response_model=EntropyResult), EntropyResult)
    assert isinstance(await client._create(response_model=CoherenceResult), CoherenceResult)
