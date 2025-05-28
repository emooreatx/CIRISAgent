import pytest
from unittest.mock import patch, MagicMock
from ciris_engine.services.llm_service import LLMService

@pytest.mark.asyncio
@patch("ciris_engine.services.llm_service.CIRISLLMClient")
async def test_llm_service_start_and_get_client(mock_client):
    service = LLMService()
    await service.start()
    client = service.get_client()
    assert client is mock_client.return_value
    await service.stop()
    with pytest.raises(RuntimeError):
        service.get_client()
