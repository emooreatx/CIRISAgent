"""Unit tests for LLM Service."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Dict, Any

from ciris_engine.logic.services.runtime.llm_service import OpenAICompatibleClient
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus
from ciris_engine.schemas.dma.results import ActionSelectionDMAResult
from ciris_engine.schemas.runtime.enums import HandlerActionType
from ciris_engine.schemas.runtime.resources import ResourceUsage
from ciris_engine.schemas.actions.parameters import SpeakParams


@pytest.fixture
def llm_service():
    """Create an LLM service for testing."""
    from ciris_engine.logic.services.runtime.llm_service import OpenAIConfig
    config = OpenAIConfig(api_key='test-key')
    return OpenAICompatibleClient(config=config)


@pytest.mark.asyncio
async def test_llm_service_lifecycle(llm_service):
    """Test LLMService start/stop lifecycle."""
    # Start
    await llm_service.start()
    # Service doesn't track running state, but should not error
    
    # Stop
    await llm_service.stop()
    # Should complete without error


@pytest.mark.asyncio
async def test_llm_service_call_structured(llm_service):
    """Test calling LLM with structured output."""
    # Mock the instructor client's response
    mock_result = ActionSelectionDMAResult(
        selected_action=HandlerActionType.SPEAK,
        action_parameters=SpeakParams(content="Test response"),
        rationale="Test response reasoning",
        reasoning="This is a test",
        evaluation_time_ms=100
    )
    
    with patch.object(llm_service.instruct_client.chat.completions, 'create', 
                     AsyncMock(return_value=mock_result)):
        
        result, usage = await llm_service.call_llm_structured(
            messages=[{"role": "user", "content": "Hello"}],
            response_model=ActionSelectionDMAResult,
            max_tokens=1024,
            temperature=0.0
        )
        
        assert isinstance(result, ActionSelectionDMAResult)
        assert result.selected_action == HandlerActionType.SPEAK
        assert result.rationale == "Test response reasoning"
        assert hasattr(usage, 'tokens_used')


@pytest.mark.asyncio
async def test_llm_service_retry_logic(llm_service):
    """Test LLM retry logic on failures."""
    # Mock to fail twice then succeed
    call_count = 0
    
    from openai import APIConnectionError
    
    async def mock_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            # APIConnectionError requires a request object
            import httpx
            request = httpx.Request(method="POST", url="https://api.openai.com/v1/chat/completions")
            raise APIConnectionError(request=request)
        
        # Create a simple dict as response
        from pydantic import BaseModel
        class TestResponse(BaseModel):
            test: str
        
        return TestResponse(test="data")
    
    with patch.object(llm_service.instruct_client.chat.completions, 'create',
                     AsyncMock(side_effect=mock_create)):
        
        from pydantic import BaseModel
        class TestResponse(BaseModel):
            test: str
            
        result, usage = await llm_service.call_llm_structured(
            messages=[{"role": "user", "content": "Test"}],
            response_model=TestResponse,
            max_tokens=1024,
            temperature=0.0
        )
        
        assert result.test == "data"
        assert call_count == 3  # Failed twice, succeeded on third


@pytest.mark.asyncio
async def test_llm_service_max_retries_exceeded(llm_service):
    """Test LLM behavior when max retries exceeded."""
    # Mock to always fail with retryable error
    from openai import APIConnectionError
    
    # APIConnectionError requires a request object
    import httpx
    request = httpx.Request(method="POST", url="https://api.openai.com/v1/chat/completions")
    
    with patch.object(llm_service.instruct_client.chat.completions, 'create',
                     AsyncMock(side_effect=APIConnectionError(request=request))):
        
        from pydantic import BaseModel
        class TestResponse(BaseModel):
            test: str
            
        with pytest.raises(APIConnectionError) as exc_info:
            await llm_service.call_llm_structured(
                messages=[{"role": "user", "content": "Test"}],
                response_model=TestResponse,
                max_tokens=1024,
                temperature=0.0
            )
        
        # APIConnectionError doesn't preserve custom message, just check it was raised
        assert "Connection error" in str(exc_info.value)


def test_llm_service_capabilities(llm_service):
    """Test LLMService.get_capabilities() returns correct info."""
    caps = llm_service.get_capabilities()
    assert isinstance(caps, ServiceCapabilities)
    assert caps.service_name == "llm_service"
    assert caps.version == "1.0.0"
    assert len(caps.actions) > 0
    assert "call_llm_structured" in caps.actions[0].lower()


def test_llm_service_status(llm_service):
    """Test LLMService.get_status() returns correct status."""
    status = llm_service.get_status()
    assert isinstance(status, ServiceStatus)
    assert status.service_name == "llm_service"
    assert status.service_type == "core_service"
    assert isinstance(status.is_healthy, bool)
    assert isinstance(status.uptime_seconds, (int, float))
    assert status.uptime_seconds >= 0
    assert isinstance(status.metrics, dict)
    assert "success_rate" in status.metrics
    assert "call_count" in status.metrics
    assert "failure_count" in status.metrics
    assert "circuit_breaker_open" in status.metrics
    # All metrics should be floats
    for key, value in status.metrics.items():
        assert isinstance(value, (int, float)), f"Metric {key} should be numeric, got {type(value)}"


@pytest.mark.asyncio
async def test_llm_service_temperature_override(llm_service):
    """Test temperature parameter override."""
    from pydantic import BaseModel
    class TestResponse(BaseModel):
        result: str
    
    mock_result = TestResponse(result="test")
    
    with patch.object(llm_service.instruct_client.chat.completions, 'create',
                     AsyncMock(return_value=mock_result)) as mock_create:
        
        result, usage = await llm_service.call_llm_structured(
            messages=[{"role": "user", "content": "Test"}],
            response_model=TestResponse,
            max_tokens=1024,
            temperature=0.5
        )
        
        # Verify temperature was passed
        call_args = mock_create.call_args[1]
        assert call_args['temperature'] == 0.5


@pytest.mark.asyncio
async def test_llm_service_model_override(llm_service):
    """Test that model is not overrideable - it uses the configured model."""
    from pydantic import BaseModel
    class TestResponse(BaseModel):
        result: str
    
    mock_result = TestResponse(result="test")
    
    with patch.object(llm_service.instruct_client.chat.completions, 'create',
                     AsyncMock(return_value=mock_result)) as mock_create:
        
        # Note: call_llm_structured doesn't accept a model parameter
        result, usage = await llm_service.call_llm_structured(
            messages=[{"role": "user", "content": "Test"}],
            response_model=TestResponse,
            max_tokens=1024,
            temperature=0.0
        )
        
        # Verify the configured model was used
        call_args = mock_create.call_args[1]
        assert call_args['model'] == llm_service.model_name


@pytest.mark.asyncio
async def test_llm_service_pydantic_response(llm_service):
    """Test LLM with Pydantic model response format."""
    from pydantic import BaseModel
    
    class TestResponse(BaseModel):
        message: str
        status: str
    
    mock_result = TestResponse(
        message="Hello",
        status="completed"
    )
    
    with patch.object(llm_service.instruct_client.chat.completions, 'create',
                     AsyncMock(return_value=mock_result)):
        
        result, usage = await llm_service.call_llm_structured(
            messages=[{"role": "user", "content": "Hi"}],
            response_model=TestResponse,
            max_tokens=1024,
            temperature=0.0
        )
        
        assert isinstance(result, TestResponse)
        assert result.message == "Hello"
        assert result.status == "completed"


@pytest.mark.asyncio
async def test_llm_service_error_handling(llm_service):
    """Test LLM error handling for various error types."""
    # Test API key error
    from ciris_engine.logic.services.runtime.llm_service import OpenAIConfig, OpenAICompatibleClient
    with pytest.raises(RuntimeError) as exc_info:
        config = OpenAIConfig(api_key='')  # Empty API key
        service = OpenAICompatibleClient(config=config)
    assert "No OpenAI API key found" in str(exc_info.value)
    
    # Test network error
    from openai import APIConnectionError
    from pydantic import BaseModel
    
    class TestResponse(BaseModel):
        test: str
    
    # APIConnectionError requires a request object
    import httpx
    request = httpx.Request(method="POST", url="https://api.openai.com/v1/chat/completions")
    
    with patch.object(llm_service.instruct_client.chat.completions, 'create',
                     AsyncMock(side_effect=APIConnectionError(request=request))):
        
        with pytest.raises(APIConnectionError):
            await llm_service.call_llm_structured(
                messages=[{"role": "user", "content": "Test"}],
                response_model=TestResponse,
                max_tokens=1024,
                temperature=0.0
            )