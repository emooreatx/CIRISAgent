import pytest
from unittest.mock import patch, MagicMock
from ciris_engine.services.llm_service import OpenAICompatibleClient
from ciris_engine.protocols.services import LLMService

@pytest.mark.asyncio
async def test_llm_service_implements_protocol():
    """Test that OpenAICompatibleClient implements LLMService protocol."""
    service = OpenAICompatibleClient()
    assert isinstance(service, LLMService)
    
    # Test that required methods exist
    assert hasattr(service, 'generate_response')
    assert hasattr(service, 'generate_structured_response')
    assert callable(service.generate_response)
    assert callable(service.generate_structured_response)
