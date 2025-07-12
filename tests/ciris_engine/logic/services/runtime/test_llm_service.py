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
    
    # Mock the OpenAI client to avoid authentication errors
    with patch('ciris_engine.logic.services.runtime.llm_service.AsyncOpenAI') as mock_openai:
        with patch('ciris_engine.logic.services.runtime.llm_service.instructor') as mock_instructor:
            # Set up mock clients
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            
            mock_instruct_client = MagicMock()
            mock_instruct_client.chat = MagicMock()
            mock_instruct_client.chat.completions = MagicMock()
            # Mock create_with_completion to return a tuple (response, completion)
            mock_instruct_client.chat.completions.create_with_completion = AsyncMock()
            mock_instructor.from_openai.return_value = mock_instruct_client
            
            config = OpenAIConfig(api_key='test-key')
            service = OpenAICompatibleClient(config=config)
            
            # Ensure the mocked clients are set
            service.client = mock_client
            service.instruct_client = mock_instruct_client
            
            # Mock the async methods
            service.start = AsyncMock()
            service.stop = AsyncMock()
            
            # Fix the exception tuples to use real exceptions
            service.retryable_exceptions = (ConnectionError, TimeoutError)
            service.non_retryable_exceptions = (ValueError, TypeError)
            
            return service


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

    # Mock the completion object with usage data
    mock_completion = MagicMock()
    mock_completion.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
    
    with patch.object(llm_service.instruct_client.chat.completions, 'create_with_completion',
                     AsyncMock(return_value=(mock_result, mock_completion))):

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

    async def mock_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            # Simulate a connection error
            raise ConnectionError("Simulated connection error for testing")

        # Create a simple dict as response
        from pydantic import BaseModel
        class TestResponse(BaseModel):
            test: str

        # Return tuple (response, completion)
        mock_completion = MagicMock()
        mock_completion.usage = MagicMock(prompt_tokens=50, completion_tokens=20)
        return TestResponse(test="data"), mock_completion

    with patch.object(llm_service.instruct_client.chat.completions, 'create_with_completion',
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
    with patch.object(llm_service.instruct_client.chat.completions, 'create_with_completion',
                     AsyncMock(side_effect=ConnectionError("Max retries exceeded"))):

        from pydantic import BaseModel
        class TestResponse(BaseModel):
            test: str

        with pytest.raises(ConnectionError) as exc_info:
            await llm_service.call_llm_structured(
                messages=[{"role": "user", "content": "Test"}],
                response_model=TestResponse,
                max_tokens=1024,
                temperature=0.0
            )

        # Check the error was raised after retries
        assert "Max retries exceeded" in str(exc_info.value)


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

    # Mock the completion object with usage data
    mock_completion = MagicMock()
    mock_completion.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
    
    with patch.object(llm_service.instruct_client.chat.completions, 'create_with_completion',
                     AsyncMock(return_value=(mock_result, mock_completion))) as mock_create:

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

    # Mock the completion object with usage data  
    mock_completion = MagicMock()
    mock_completion.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
    
    with patch.object(llm_service.instruct_client.chat.completions, 'create_with_completion',
                     AsyncMock(return_value=(mock_result, mock_completion))) as mock_create:

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

    # Mock the completion object with usage data  
    mock_completion = MagicMock()
    mock_completion.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
    
    with patch.object(llm_service.instruct_client.chat.completions, 'create_with_completion',
                     AsyncMock(return_value=(mock_result, mock_completion))):

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
    
    # Mock the OpenAI client to simulate the error
    with patch('ciris_engine.logic.services.runtime.llm_service.AsyncOpenAI') as mock_openai:
        mock_openai.side_effect = RuntimeError("No OpenAI API key found")
        
        with pytest.raises(RuntimeError) as exc_info:
            config = OpenAIConfig(api_key='')  # Empty API key
            service = OpenAICompatibleClient(config=config)
        # The error message changed in newer versions
        assert "No OpenAI API key found" in str(exc_info.value)

    # Test network error
    from pydantic import BaseModel

    class TestResponse(BaseModel):
        test: str

    with patch.object(llm_service.instruct_client.chat.completions, 'create_with_completion',
                     AsyncMock(side_effect=ConnectionError("Network error"))):

        with pytest.raises(ConnectionError):
            await llm_service.call_llm_structured(
                messages=[{"role": "user", "content": "Test"}],
                response_model=TestResponse,
                max_tokens=1024,
                temperature=0.0
            )
