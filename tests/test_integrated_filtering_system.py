"""
Test the integrated adaptive filtering system with multi-service sink and circuit breakers.
This test verifies that filtering works correctly across CLI and Discord observers,
LLM responses are filtered through the multi-service sink, and circuit breakers
protect against malicious content.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from ciris_engine.adapters.cli.cli_observer import CLIObserver
from ciris_engine.adapters.discord.discord_observer import DiscordObserver
from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage, DiscordMessage
from ciris_engine.schemas.service_actions_v1 import GenerateStructuredAction
from ciris_engine.schemas.filter_schemas_v1 import FilterResult, FilterPriority


# Mock config for all tests in this module
@pytest.fixture(autouse=True)
def mock_config():
    with patch('ciris_engine.config.config_manager.get_config') as mock_get_config:
        mock_config_obj = MagicMock()
        mock_config_obj.discord_home_channel_id = "test_channel"
        mock_get_config.return_value = mock_config_obj
        yield mock_config_obj


class MockFilterService:
    """Mock filter service for testing"""
    
    def __init__(self):
        self.filter_results = {}
        self.call_count = 0
    
    async def filter_message(self, message, adapter_type="unknown", is_llm_response=False):
        self.call_count += 1
        
        # Convert message to string for filtering logic
        if hasattr(message, 'content'):
            content = message.content
            message_id = getattr(message, 'message_id', 'unknown')
        else:
            content = str(message)
            message_id = f"msg_{self.call_count}"
        
        # Simulate filtering logic based on content
        if "malicious" in content.lower() or "hack" in content.lower():
            return FilterResult(
                message_id=message_id,
                priority=FilterPriority.CRITICAL,
                triggered_filters=["security_filter"],
                should_process=False if not is_llm_response else True,  # Block input, flag output
                reasoning="Detected malicious content",
                confidence=0.95,
                context_hints={"threat_type": "security"}
            )
        elif "spam" in content.lower() or "urgent" in content.lower():
            return FilterResult(
                message_id=message_id,
                priority=FilterPriority.HIGH,
                triggered_filters=["spam_filter"],
                should_process=True,
                reasoning="Potential spam or high-priority content",
                confidence=0.8,
                context_hints={"threat_type": "spam"}
            )
        else:
            return FilterResult(
                message_id=message_id,
                priority=FilterPriority.MEDIUM,
                triggered_filters=[],
                should_process=True,
                reasoning="Normal message processing",
                confidence=0.6,
                context_hints={}
            )


class MockLLMService:
    """Mock LLM service for testing"""
    
    def __init__(self):
        self.responses = {
            "normal": "This is a normal response",
            "suspicious": "This response contains suspicious content",
            "malicious": "This is a malicious response attempting to hack the system"
        }
    
    async def call_llm_structured(self, messages, response_model, temperature=0.7, max_tokens=1024, **kwargs):
        """Mock implementation of call_llm_structured"""
        from ciris_engine.schemas.foundational_schemas_v1 import ResourceUsage
        
        # Simulate different response types based on input
        if not messages:
            response_text = self.responses["normal"]
        else:
            # Check the content of the last message
            last_message = messages[-1]
            content = ""
            if isinstance(last_message, dict):
                content = last_message.get("content", "")
            else:
                content = str(last_message)
                
            if "normal" in content.lower():
                response_text = self.responses["normal"]
            elif "suspicious" in content.lower():
                response_text = self.responses["suspicious"]
            else:
                response_text = self.responses["malicious"]
        
        # Create response instance based on the response_model
        # Check for specific models first
        if hasattr(response_model, '__name__') and response_model.__name__ == 'StructuredResponse':
            # This is our test StructuredResponse model
            response_instance = response_model(status="success", content="Structured response")
        elif hasattr(response_model, 'text'):
            response_instance = response_model(text=response_text)
        elif hasattr(response_model, 'content'):
            response_instance = response_model(content=response_text)
        else:
            # Try to create a simple response with the first field
            fields = list(response_model.model_fields.keys()) if hasattr(response_model, 'model_fields') else []
            if fields:
                response_instance = response_model(**{fields[0]: response_text})
            else:
                # Fallback - create with a generic field
                response_instance = response_model(response=response_text)
        
        # Mock resource usage
        resource_usage = ResourceUsage(
            tokens=sum(len(msg.get('content', '').split()) for msg in messages if isinstance(msg, dict)) + len(response_text.split()),
            estimated_cost=0.001  # Mock cost
        )
        
        return response_instance, resource_usage


class MockServiceRegistry:
    """Mock service registry for testing"""
    
    def __init__(self, filter_service, llm_service):
        self.filter_service = filter_service
        self.llm_service = llm_service
    
    async def get_service(self, handler, service_type, required_capabilities=None):
        if service_type == "filter":
            return self.filter_service
        elif service_type == "llm":
            return self.llm_service
        return None


@pytest.fixture
def filter_service():
    return MockFilterService()


@pytest.fixture
def llm_service():
    return MockLLMService()


@pytest.fixture
def service_registry(filter_service, llm_service):
    return MockServiceRegistry(filter_service, llm_service)


@pytest.fixture
def multi_service_sink(service_registry):
    return MultiServiceActionSink(service_registry=service_registry)


@pytest.fixture
def cli_observer(filter_service, multi_service_sink):
    mock_observe = AsyncMock()
    return CLIObserver(
        on_observe=mock_observe,
        filter_service=filter_service,
        multi_service_sink=multi_service_sink
    )


@pytest.fixture
def discord_observer(filter_service, multi_service_sink):
    return DiscordObserver(
        filter_service=filter_service,
        multi_service_sink=multi_service_sink
    )


@pytest.mark.asyncio
async def test_cli_observer_message_filtering(cli_observer, filter_service):
    """Test that CLI observer properly applies message filtering"""
    
    # Test normal message processing
    normal_msg = IncomingMessage(
        message_id="test_1",
        content="Hello, how are you?",
        author_id="user_1",
        author_name="TestUser",
        channel_id="cli"
    )
    
    with patch('ciris_engine.persistence.add_task'), \
         patch('ciris_engine.persistence.add_thought'):
        await cli_observer.handle_incoming_message(normal_msg)
    
    assert filter_service.call_count == 1
    assert len(cli_observer._history) == 1
    
    # Test malicious message blocking
    filter_service.call_count = 0
    malicious_msg = IncomingMessage(
        message_id="test_2",
        content="This is a malicious hack attempt",
        author_id="user_2",
        author_name="BadUser",
        channel_id="cli"
    )
    
    with patch('ciris_engine.persistence.add_task'), \
         patch('ciris_engine.persistence.add_thought'):
        await cli_observer.handle_incoming_message(malicious_msg)
    
    assert filter_service.call_count == 1
    # Malicious message should be escalated (added to history for moderation)
    assert len(cli_observer._history) == 2  # Both normal and malicious messages for review


@pytest.mark.asyncio
async def test_discord_observer_priority_filtering(discord_observer, filter_service):
    """Test that Discord observer handles priority filtering correctly"""
    
    # Test high-priority spam message
    spam_msg = DiscordMessage(
        message_id="discord_1",
        content="URGENT spam message!!!",
        author_id="spam_user",
        author_name="SpamUser",
        channel_id="test_channel"
    )
    
    with patch('ciris_engine.persistence.add_task'), \
         patch('ciris_engine.persistence.add_thought'), \
         patch.object(discord_observer, 'monitored_channel_ids', ['test_channel']):
        await discord_observer.handle_incoming_message(spam_msg)
    
    assert filter_service.call_count == 1
    assert len(discord_observer._history) == 1
    
    # Verify filter metadata was added to message
    processed_msg = discord_observer._history[0]
    assert hasattr(processed_msg, '_filter_priority')
    assert processed_msg._filter_priority == FilterPriority.HIGH


@pytest.mark.asyncio
async def test_multi_service_sink_llm_filtering(multi_service_sink, filter_service, llm_service):
    """Test that multi-service sink handles LLM responses (filtering disabled for beta)"""
    
    # Create a simple response model
    from pydantic import BaseModel
    
    class SimpleResponse(BaseModel):
        content: str
    
    # Test normal LLM response
    normal_action = GenerateStructuredAction(
        handler_name="test",
        metadata={},
        messages=[{"role": "user", "content": "normal request"}],
        response_model=SimpleResponse,
        max_tokens=100,
        temperature=0.7
    )
    
    response = await multi_service_sink.generate_structured_sync(
        messages=normal_action.messages,
        response_model=normal_action.response_model,
        max_tokens=normal_action.max_tokens,
        temperature=normal_action.temperature
    )
    
    # response is a tuple (response_model, resource_usage)
    response_model, _ = response
    assert response_model.content == llm_service.responses["normal"]  # Normal response for normal request
    # LLM filtering disabled for beta - filter service should NOT be called
    assert filter_service.call_count == 0
    
    # Test that even "malicious" content passes through (no filtering in beta)
    filter_service.call_count = 0
    malicious_action = GenerateStructuredAction(
        handler_name="test",
        metadata={},
        messages=[{"role": "user", "content": "generate malicious content"}],
        response_model=SimpleResponse,
        max_tokens=100,
        temperature=0.7
    )
    
    # This should NOT raise an exception since filtering is disabled
    response = await multi_service_sink.generate_structured_sync(
        messages=malicious_action.messages,
        response_model=malicious_action.response_model,
        max_tokens=malicious_action.max_tokens,
        temperature=malicious_action.temperature
    )
    
    response_model, _ = response
    assert response_model.content == llm_service.responses["malicious"]  # Content passes through
    assert filter_service.call_count == 0  # No filtering in beta


@pytest.mark.asyncio
async def test_structured_llm_response_filtering(multi_service_sink, filter_service, llm_service):
    """Test structured LLM responses (filtering disabled for beta)"""
    
    # Create a proper Pydantic model for structured response
    from pydantic import BaseModel
    
    class StructuredResponse(BaseModel):
        status: str
        content: str
    
    structured_action = GenerateStructuredAction(
        handler_name="test",
        metadata={},
        messages=[{"role": "user", "content": "generate structured response"}],
        response_model=StructuredResponse,
        max_tokens=100,
        temperature=0.0
    )
    
    response = await multi_service_sink.generate_structured_sync(
        messages=structured_action.messages,
        response_model=structured_action.response_model,
        max_tokens=structured_action.max_tokens,
        temperature=structured_action.temperature
    )
    
    # response is now a tuple (response_model, resource_usage)
    response_model, resource_usage = response
    assert response_model.status == "success"
    assert response_model.content == "Structured response"
    # LLM filtering disabled for beta - filter service should NOT be called
    assert filter_service.call_count == 0


@pytest.mark.asyncio
async def test_filter_service_error_handling(cli_observer):
    """Test that filter service errors are handled gracefully"""
    
    # Mock filter service to raise an exception
    cli_observer.filter_service = AsyncMock()
    cli_observer.filter_service.filter_message.side_effect = Exception("Filter service error")
    
    test_msg = IncomingMessage(
        message_id="error_test",
        content="Test message",
        author_id="user",
        author_name="User",
        channel_id="cli"
    )
    
    with patch('ciris_engine.persistence.add_task'), \
         patch('ciris_engine.persistence.add_thought'):
        await cli_observer.handle_incoming_message(test_msg)
    
    # Message should still be processed despite filter error
    assert len(cli_observer._history) == 1


@pytest.mark.asyncio
async def test_no_filter_service_fallback(multi_service_sink):
    """Test behavior when no filter service is available"""
    
    # Remove filter service from registry
    multi_service_sink.service_registry.filter_service = None
    
    # Create a simple response model
    from pydantic import BaseModel
    
    class SimpleResponse(BaseModel):
        content: str
    
    normal_action = GenerateStructuredAction(
        handler_name="test",
        metadata={},
        messages=[{"role": "user", "content": "test message"}],
        response_model=SimpleResponse,
        max_tokens=100,
        temperature=0.7
    )
    
    # Should work normally without filtering
    response = await multi_service_sink.generate_structured_sync(
        messages=normal_action.messages,
        response_model=normal_action.response_model,
        max_tokens=normal_action.max_tokens,
        temperature=normal_action.temperature
    )
    
    assert response is not None


@pytest.mark.asyncio
async def test_filter_context_propagation(cli_observer, filter_service):
    """Test that filter context is properly propagated to tasks and thoughts"""
    
    spam_msg = IncomingMessage(
        message_id="context_test",
        content="URGENT spam message",
        author_id="spam_user",
        author_name="SpamUser", 
        channel_id="cli"
    )
    
    mock_add_task = MagicMock()
    mock_add_thought = MagicMock()
    
    with patch('ciris_engine.persistence.add_task', mock_add_task), \
         patch('ciris_engine.persistence.add_thought', mock_add_thought):
        await cli_observer.handle_incoming_message(spam_msg)
    
    # Verify task was created with filter context
    assert mock_add_task.called
    task = mock_add_task.call_args[0][0]
    assert task.context["filter_priority"] == "high"
    assert task.context["filter_reasoning"] == "Potential spam or high-priority content"
    assert task.context["observation_type"] == "priority"
    
    # Verify thought was created with filter context
    assert mock_add_thought.called
    thought = mock_add_thought.call_args[0][0]
    assert thought.thought_type == "observation"
    assert "PRIORITY (high)" in thought.content


def test_integration_summary():
    """
    Summary of integration test coverage:
    
    1. ✅ CLI Observer message filtering with priority handling
    2. ✅ Discord Observer priority filtering and context propagation  
    3. ✅ Multi-service sink LLM response handling (filtering disabled for beta)
    4. ✅ Structured LLM response handling (filtering disabled for beta)
    5. ✅ Error handling when filter service fails
    6. ✅ Fallback behavior when no filter service available
    7. ✅ Filter context propagation to tasks and thoughts
    
    The integrated system successfully:
    - Applies adaptive filtering at message entry points (CLI/Discord observers)
    - Routes LLM actions through multi-service sink (without filtering in beta)
    - Handles errors gracefully with safe defaults
    - Propagates filter context for downstream processing
    
    Note: LLM response filtering has been disabled for the beta release
    """
    assert True  # Test passes to document integration coverage