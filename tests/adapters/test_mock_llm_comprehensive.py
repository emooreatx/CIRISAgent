"""
Comprehensive test for the mock LLM service to verify response schema compatibility.
"""
import pytest
import json

from tests.adapters.mock_llm import MockLLMClient
from ciris_engine.schemas.dma_results_v1 import (
    EthicalDMAResult, CSDMAResult, DSDMAResult, ActionSelectionResult
)
from ciris_engine.schemas.feedback_schemas_v1 import (
    OptimizationVetoResult, EpistemicHumilityResult
)
from ciris_engine.schemas.faculty_schemas_v1 import EntropyResult, CoherenceResult
from ciris_engine.dma.dsdma_base import BaseDSDMA


class TestMockLLMComprehensive:
    """Test that all mock LLM responses have proper structure for instructor library."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock LLM client for testing."""
        return MockLLMClient()
    
    @pytest.mark.asyncio
    async def test_ethical_dma_result(self, mock_client):
        """Test EthicalDMAResult schema response."""
        response = await mock_client._create(response_model=EthicalDMAResult)
        
        assert isinstance(response, EthicalDMAResult)
        assert hasattr(response, 'choices')
        assert hasattr(response, 'finish_reason')
        assert hasattr(response, '_raw_response')
        
        # Verify the response has expected fields
        assert hasattr(response, 'alignment_check')
        assert hasattr(response, 'decision')
    
    @pytest.mark.asyncio
    async def test_cs_dma_result(self, mock_client):
        """Test CSDMAResult schema response."""
        response = await mock_client._create(response_model=CSDMAResult)
        
        assert isinstance(response, CSDMAResult)
        assert hasattr(response, 'choices')
        assert hasattr(response, 'finish_reason')
        assert hasattr(response, '_raw_response')
        
        # Verify the response has expected fields
        assert hasattr(response, 'plausibility_score')
        assert hasattr(response, 'flags')
    
    @pytest.mark.asyncio
    async def test_ds_dma_result(self, mock_client):
        """Test DSDMAResult schema response."""
        response = await mock_client._create(response_model=DSDMAResult)
        
        assert isinstance(response, DSDMAResult)
        assert hasattr(response, 'choices')
        assert hasattr(response, 'finish_reason')
        assert hasattr(response, '_raw_response')
        
        # Verify the response has expected fields
        assert hasattr(response, 'domain')
        assert hasattr(response, 'score')
    
    @pytest.mark.asyncio
    async def test_action_selection_result(self, mock_client):
        """Test ActionSelectionResult schema response."""
        response = await mock_client._create(response_model=ActionSelectionResult)
        
        assert isinstance(response, ActionSelectionResult)
        assert hasattr(response, 'choices')
        assert hasattr(response, 'finish_reason')
        assert hasattr(response, '_raw_response')
        
        # Verify the response has expected fields
        assert hasattr(response, 'selected_action')
        assert hasattr(response, 'action_parameters')
        assert hasattr(response, 'rationale')
    
    @pytest.mark.asyncio
    async def test_dsdma_llm_output(self, mock_client):
        """Test BaseDSDMA.LLMOutputForDSDMA schema response."""
        response = await mock_client._create(response_model=BaseDSDMA.LLMOutputForDSDMA)
        
        assert isinstance(response, BaseDSDMA.LLMOutputForDSDMA)
        assert hasattr(response, 'choices')
        assert hasattr(response, 'finish_reason')
        assert hasattr(response, '_raw_response')
    
    @pytest.mark.asyncio
    async def test_optimization_veto_result(self, mock_client):
        """Test OptimizationVetoResult schema response."""
        response = await mock_client._create(response_model=OptimizationVetoResult)
        
        assert isinstance(response, OptimizationVetoResult)
        assert hasattr(response, 'choices')
        assert hasattr(response, 'finish_reason')
        assert hasattr(response, '_raw_response')
        
        # Verify the response has expected fields
        assert hasattr(response, 'decision')
        assert hasattr(response, 'justification')
    
    @pytest.mark.asyncio
    async def test_epistemic_humility_result(self, mock_client):
        """Test EpistemicHumilityResult schema response."""
        response = await mock_client._create(response_model=EpistemicHumilityResult)
        
        assert isinstance(response, EpistemicHumilityResult)
        assert hasattr(response, 'choices')
        assert hasattr(response, 'finish_reason')
        assert hasattr(response, '_raw_response')
        
        # Verify the response has expected fields
        assert hasattr(response, 'epistemic_certainty')
        assert hasattr(response, 'reflective_justification')
    
    @pytest.mark.asyncio
    async def test_entropy_result(self, mock_client):
        """Test EntropyResult schema response."""
        response = await mock_client._create(response_model=EntropyResult)
        
        assert isinstance(response, EntropyResult)
        assert hasattr(response, 'choices')
        assert hasattr(response, 'finish_reason')
        assert hasattr(response, '_raw_response')
        
        # Verify the response has expected fields
        assert hasattr(response, 'entropy')
    
    @pytest.mark.asyncio
    async def test_coherence_result(self, mock_client):
        """Test CoherenceResult schema response."""
        response = await mock_client._create(response_model=CoherenceResult)
        
        assert isinstance(response, CoherenceResult)
        assert hasattr(response, 'choices')
        assert hasattr(response, 'finish_reason')
        assert hasattr(response, '_raw_response')
        
        # Verify the response has expected fields
        assert hasattr(response, 'coherence')
    
    @pytest.mark.asyncio
    async def test_all_schemas_serializable(self, mock_client):
        """Test that all schema responses can be serialized to JSON."""
        test_schemas = [
            EthicalDMAResult,
            CSDMAResult, 
            DSDMAResult,
            BaseDSDMA.LLMOutputForDSDMA,
            OptimizationVetoResult,
            EpistemicHumilityResult,
            ActionSelectionResult,
            EntropyResult,
            CoherenceResult
        ]
        
        for schema in test_schemas:
            response = await mock_client._create(response_model=schema)
            
            # Test that the response can be converted to dict and serialized
            try:
                if hasattr(response, 'model_dump'):
                    response_dict = response.model_dump(mode="json")
                    json.dumps(response_dict)
                else:
                    # Fallback for objects without model_dump
                    json.dumps(response, default=str)
            except (TypeError, ValueError) as e:
                pytest.fail(f"Schema {schema.__name__} response not serializable: {e}")
    
    @pytest.mark.asyncio
    async def test_mock_response_consistency(self, mock_client):
        """Test that mock responses are consistent across multiple calls."""
        # Test with ActionSelectionResult
        response1 = await mock_client._create(response_model=ActionSelectionResult)
        response2 = await mock_client._create(response_model=ActionSelectionResult)
        
        # Both should be valid instances
        assert isinstance(response1, ActionSelectionResult)
        assert isinstance(response2, ActionSelectionResult)
        
        # Both should have required instructor attributes
        for response in [response1, response2]:
            assert hasattr(response, 'choices')
            assert hasattr(response, 'finish_reason')
            assert hasattr(response, '_raw_response')
