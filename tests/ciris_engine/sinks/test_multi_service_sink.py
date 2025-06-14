"""
Comprehensive unit tests for MultiServiceActionSink.

Tests the multi-service action routing sink that handles various action types
and delegates them to appropriate services with fallback support.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List, Optional

from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink
from ciris_engine.schemas.service_actions_v1 import (
    ActionType,
    ActionMessage,
    SendMessageAction,
    FetchMessagesAction,
    FetchGuidanceAction,
    SendDeferralAction,
    MemorizeAction,
    RecallAction,
    ForgetAction,
    SendToolAction,
    FetchToolAction,
    GenerateResponseAction,
    GenerateStructuredAction,
)
from ciris_engine.schemas.foundational_schemas_v1 import FetchedMessage
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpStatus, MemoryOpResult
from ciris_engine.schemas.tool_schemas_v1 import ToolResult, ToolExecutionStatus
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope
from ciris_engine.protocols.services import (
    CommunicationService,
    WiseAuthorityService,
    MemoryService,
    ToolService,
    LLMService,
)


class TestMultiServiceActionSink:
    """Test suite for MultiServiceActionSink functionality."""

    @pytest.fixture
    def service_registry(self):
        """Create a mock service registry."""
        registry = AsyncMock()
        return registry

    @pytest.fixture
    def sink(self, service_registry):
        """Create a MultiServiceActionSink instance with mocked registry."""
        return MultiServiceActionSink(
            service_registry=service_registry,
            max_queue_size=100,
            fallback_channel_id="test_channel"
        )

    @pytest.fixture
    def mock_communication_service(self):
        """Create a mock communication service."""
        service = AsyncMock(spec=CommunicationService)
        service.send_message.return_value = True
        service.fetch_messages.return_value = [
            FetchedMessage(
                message_id="msg1",
                content="Hello world",
                author="user1",
                timestamp="2024-01-01T00:00:00Z",
                channel_id="test_channel"
            )
        ]
        return service

    @pytest.fixture
    def mock_wise_authority_service(self):
        """Create a mock wise authority service."""
        service = AsyncMock(spec=WiseAuthorityService)
        service.fetch_guidance.return_value = "Test guidance"
        service.send_deferral.return_value = True
        return service

    @pytest.fixture
    def mock_memory_service(self):
        """Create a mock memory service."""
        service = AsyncMock(spec=MemoryService)
        service.memorize.return_value = MemoryOpResult(
            status=MemoryOpStatus.OK,
            data={"stored": True}
        )
        service.recall.return_value = MemoryOpResult(
            status=MemoryOpStatus.OK,
            data={"content": "recalled data"}
        )
        service.forget.return_value = MemoryOpResult(
            status=MemoryOpStatus.OK,
            data={"deleted": True}
        )
        return service

    @pytest.fixture
    def mock_tool_service(self):
        """Create a mock tool service."""
        service = AsyncMock(spec=ToolService)
        service.execute_tool.return_value = ToolResult(
            tool_name="test_tool",
            execution_status=ToolExecutionStatus.SUCCESS,
            result_data={"output": "tool result"}
        )
        service.get_tool_result.return_value = ToolResult(
            tool_name="test_tool",
            execution_status=ToolExecutionStatus.SUCCESS,
            result_data={"cached_output": "cached result"}
        )
        return service

    @pytest.fixture
    def mock_llm_service(self):
        """Create a mock LLM service."""
        from pydantic import BaseModel
        from ciris_engine.schemas.foundational_schemas_v1 import ResourceUsage
        
        service = AsyncMock(spec=LLMService)
        
        # Mock text response
        class TextResponse(BaseModel):
            text: str = "Generated response"
        
        # Mock structured response 
        class StructuredResponse(BaseModel):
            structured: str = "response"
        
        # Mock call_llm_structured to return appropriate responses
        def mock_call_llm_structured(messages, response_model, **kwargs):
            if hasattr(response_model, '__name__') and 'Text' in response_model.__name__:
                return TextResponse(), ResourceUsage(tokens=100)
            else:
                return StructuredResponse(), ResourceUsage(tokens=100)
        
        service.call_llm_structured.side_effect = mock_call_llm_structured
        return service

    def test_service_routing_property(self, sink):
        """Test that service routing maps action types to correct service types."""
        routing = sink.service_routing
        
        assert routing[ActionType.SEND_MESSAGE] == 'communication'
        assert routing[ActionType.FETCH_MESSAGES] == 'communication'
        assert routing[ActionType.FETCH_GUIDANCE] == 'wise_authority'
        assert routing[ActionType.SEND_DEFERRAL] == 'wise_authority'
        assert routing[ActionType.MEMORIZE] == 'memory'
        assert routing[ActionType.RECALL] == 'memory'
        assert routing[ActionType.FORGET] == 'memory'
        assert routing[ActionType.SEND_TOOL] == 'tool'
        assert routing[ActionType.FETCH_TOOL] == 'tool'
        assert routing[ActionType.GENERATE_RESPONSE] == 'llm'
        assert routing[ActionType.GENERATE_STRUCTURED] == 'llm'

    def test_capability_map_property(self, sink):
        """Test that capability map maps action types to required capabilities."""
        capabilities = sink.capability_map
        
        assert capabilities[ActionType.SEND_MESSAGE] == ['send_message']
        assert capabilities[ActionType.FETCH_MESSAGES] == ['fetch_messages']
        assert capabilities[ActionType.FETCH_GUIDANCE] == ['fetch_guidance']
        assert capabilities[ActionType.SEND_DEFERRAL] == ['send_deferral']
        assert capabilities[ActionType.MEMORIZE] == ['memorize']
        assert capabilities[ActionType.RECALL] == ['recall']
        assert capabilities[ActionType.FORGET] == ['forget']
        assert capabilities[ActionType.SEND_TOOL] == ['execute_tool']
        assert capabilities[ActionType.FETCH_TOOL] == ['get_tool_result']
        assert capabilities[ActionType.GENERATE_RESPONSE] == ['call_llm_structured']
        assert capabilities[ActionType.GENERATE_STRUCTURED] == ['call_llm_structured']

    @pytest.mark.asyncio
    async def test_validate_action_send_message(self, sink):
        """Test action validation for send message actions."""
        # Valid send message action
        valid_action = SendMessageAction(
            handler_name="test",
            metadata={},
            channel_id="test_channel",
            content="Hello world"
        )
        assert await sink._validate_action(valid_action) is True
        
        # Invalid - missing channel_id
        invalid_action1 = SendMessageAction(
            handler_name="test",
            metadata={},
            channel_id="",
            content="Hello world"
        )
        assert await sink._validate_action(invalid_action1) is False
        
        # Invalid - missing content
        invalid_action2 = SendMessageAction(
            handler_name="test",
            metadata={},
            channel_id="test_channel",
            content=""
        )
        assert await sink._validate_action(invalid_action2) is False

    @pytest.mark.asyncio
    async def test_validate_action_send_deferral(self, sink):
        """Test action validation for send deferral actions."""
        # Valid deferral action
        valid_action = SendDeferralAction(
            handler_name="test",
            metadata={},
            thought_id="thought_123",
            reason="Need more information"
        )
        assert await sink._validate_action(valid_action) is True
        
        # Invalid - missing thought_id
        invalid_action1 = SendDeferralAction(
            handler_name="test",
            metadata={},
            thought_id="",
            reason="Need more information"
        )
        assert await sink._validate_action(invalid_action1) is False
        
        # Invalid - missing reason
        invalid_action2 = SendDeferralAction(
            handler_name="test",
            metadata={},
            thought_id="thought_123",
            reason=""
        )
        assert await sink._validate_action(invalid_action2) is False

    @pytest.mark.asyncio
    async def test_validate_action_other_types(self, sink):
        """Test that other action types always validate as true."""
        test_node = GraphNode(
            id="test_node",
            type=NodeType.CONCEPT,
            scope=GraphScope.LOCAL
        )
        
        actions = [
            FetchMessagesAction("test", {}, "channel", 10),
            FetchGuidanceAction("test", {}, {"context": "test"}),
            MemorizeAction("test", {}, test_node),
            RecallAction("test", {}, test_node),
            ForgetAction("test", {}, test_node),
            SendToolAction("test", {}, "test_tool", {}),
            FetchToolAction("test", {}, "test_tool", "corr_123"),
            GenerateResponseAction("test", {}, []),
            GenerateStructuredAction("test", {}, [], {})
        ]
        
        for action in actions:
            assert await sink._validate_action(action) is True

    @pytest.mark.asyncio
    async def test_handle_send_message(self, sink, mock_communication_service):
        """Test send message handling."""
        action = SendMessageAction(
            handler_name="test",
            metadata={},
            channel_id="test_channel",
            content="Hello world"
        )
        
        await sink._handle_send_message(mock_communication_service, action)
        
        mock_communication_service.send_message.assert_awaited_once_with(
            "test_channel", "Hello world"
        )

    @pytest.mark.asyncio
    async def test_handle_fetch_messages(self, sink, mock_communication_service):
        """Test fetch messages handling."""
        action = FetchMessagesAction(
            handler_name="test",
            metadata={},
            channel_id="test_channel",
            limit=5
        )
        
        result = await sink._handle_fetch_messages(mock_communication_service, action)
        
        mock_communication_service.fetch_messages.assert_awaited_once_with(
            "test_channel", 5
        )
        assert len(result) == 1
        assert result[0].content == "Hello world"

    @pytest.mark.asyncio
    async def test_handle_fetch_guidance(self, sink, mock_wise_authority_service):
        """Test fetch guidance handling."""
        action = FetchGuidanceAction(
            handler_name="test",
            metadata={},
            context={"situation": "need help"}
        )
        
        result = await sink._handle_fetch_guidance(mock_wise_authority_service, action)
        
        mock_wise_authority_service.fetch_guidance.assert_awaited_once_with(
            {"situation": "need help"}
        )
        assert result == "Test guidance"

    @pytest.mark.asyncio
    async def test_handle_send_deferral(self, sink, mock_wise_authority_service):
        """Test send deferral handling."""
        action = SendDeferralAction(
            handler_name="test",
            metadata={},
            thought_id="thought_123",
            reason="Need more time"
        )
        
        await sink._handle_send_deferral(mock_wise_authority_service, action)
        
        mock_wise_authority_service.send_deferral.assert_awaited_once_with(
            "thought_123", "Need more time"
        )

    @pytest.mark.asyncio
    async def test_handle_memorize(self, sink, mock_memory_service):
        """Test memorize handling."""
        test_node = GraphNode(
            id="test_node",
            type=NodeType.CONCEPT,
            scope=GraphScope.LOCAL
        )
        
        action = MemorizeAction(
            handler_name="test",
            metadata={},
            node=test_node
        )
        
        result = await sink._handle_memorize(mock_memory_service, action)
        
        mock_memory_service.memorize.assert_awaited_once_with(test_node)
        assert result.status == MemoryOpStatus.OK

    @pytest.mark.asyncio
    async def test_handle_recall(self, sink, mock_memory_service):
        """Test recall handling."""
        test_node = GraphNode(
            id="test_node",
            type=NodeType.CONCEPT,
            scope=GraphScope.LOCAL
        )
        
        action = RecallAction(
            handler_name="test",
            metadata={},
            node=test_node
        )
        
        result = await sink._handle_recall(mock_memory_service, action)
        
        mock_memory_service.recall.assert_awaited_once_with(test_node)
        assert result.status == MemoryOpStatus.OK

    @pytest.mark.asyncio
    async def test_handle_forget(self, sink, mock_memory_service):
        """Test forget handling."""
        test_node = GraphNode(
            id="test_node",
            type=NodeType.CONCEPT,
            scope=GraphScope.LOCAL
        )
        
        action = ForgetAction(
            handler_name="test",
            metadata={},
            node=test_node
        )
        
        result = await sink._handle_forget(mock_memory_service, action)
        
        mock_memory_service.forget.assert_awaited_once_with(test_node)
        assert result.status == MemoryOpStatus.OK

    @pytest.mark.asyncio
    async def test_handle_send_tool(self, sink, mock_tool_service):
        """Test send tool handling."""
        action = SendToolAction(
            handler_name="test",
            metadata={},
            tool_name="test_tool",
            tool_args={"param": "value"},
            correlation_id="corr_123"
        )
        
        result = await sink._handle_send_tool(mock_tool_service, action)
        
        mock_tool_service.execute_tool.assert_awaited_once_with(
            "test_tool", {"param": "value"}
        )
        assert result.execution_status == ToolExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_handle_fetch_tool(self, sink, mock_tool_service):
        """Test fetch tool handling."""
        action = FetchToolAction(
            handler_name="test",
            metadata={},
            tool_name="test_tool",
            correlation_id="corr_123",
            timeout=30.0
        )
        
        result = await sink._handle_fetch_tool(mock_tool_service, action)
        
        mock_tool_service.get_tool_result.assert_awaited_once_with(
            "corr_123", 30.0
        )
        assert result.execution_status == ToolExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_handle_generate_response(self, sink, mock_llm_service):
        """Test generate response handling."""
        messages = [{"role": "user", "content": "Hello"}]
        action = GenerateResponseAction(
            handler_name="test",
            metadata={},
            messages=messages,
            temperature=0.7,
            max_tokens=100
        )
        
        with patch.object(sink, '_get_filter_service', return_value=None):
            result = await sink._handle_generate_response(mock_llm_service, action)
        
        mock_llm_service.call_llm_structured.assert_awaited_once()
        assert result == "Generated response"

    @pytest.mark.asyncio
    async def test_handle_generate_structured(self, sink, mock_llm_service):
        """Test generate structured response handling."""
        messages = [{"role": "user", "content": "Generate structured data"}]
        response_model = {"type": "object", "properties": {"answer": {"type": "string"}}}
        
        action = GenerateStructuredAction(
            handler_name="test",
            metadata={},
            messages=messages,
            response_model=response_model
        )
        
        with patch.object(sink, '_get_filter_service', return_value=None):
            result = await sink._handle_generate_structured(mock_llm_service, action)
        
        mock_llm_service.call_llm_structured.assert_awaited()
        response_model, resource_usage = result
        assert response_model.structured == "response"

    @pytest.mark.asyncio
    async def test_convenience_method_send_message(self, sink):
        """Test send_message convenience method."""
        with patch.object(sink, 'enqueue_action', return_value=True) as mock_enqueue:
            result = await sink.send_message(
                "test_handler", "test_channel", "Hello world", {"meta": "data"}
            )
            
            assert result is True
            mock_enqueue.assert_awaited_once()
            action = mock_enqueue.call_args[0][0]
            assert isinstance(action, SendMessageAction)
            assert action.channel_id == "test_channel"
            assert action.content == "Hello world"

    @pytest.mark.asyncio
    async def test_convenience_method_fetch_messages_sync(self, sink, mock_communication_service):
        """Test fetch_messages_sync convenience method."""
        with patch.object(sink, '_get_service', return_value=mock_communication_service):
            result = await sink.fetch_messages_sync("test_handler", "test_channel", 5)
            
            assert len(result) == 1
            assert result[0].content == "Hello world"

    @pytest.mark.asyncio
    async def test_convenience_method_execute_tool_sync(self, sink, mock_tool_service):
        """Test execute_tool_sync convenience method."""
        with patch.object(sink, '_get_service', return_value=mock_tool_service):
            result = await sink.execute_tool_sync(
                "test_tool", {"param": "value"}, "corr_123"
            )
            
            assert isinstance(result, ToolResult)
            assert result.execution_status == ToolExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_convenience_method_memorize_sync(self, sink, mock_memory_service):
        """Test memorize convenience method."""
        test_node = GraphNode(
            id="test_node",
            type=NodeType.CONCEPT,
            scope=GraphScope.LOCAL
        )
        
        with patch.object(sink, '_get_service', return_value=mock_memory_service):
            result = await sink.memorize(test_node)
            
            assert result.status == MemoryOpStatus.OK

    @pytest.mark.asyncio
    async def test_convenience_method_generate_response_sync(self, sink, mock_llm_service):
        """Test generate_response_sync convenience method."""
        messages = [{"role": "user", "content": "Hello"}]
        
        with patch.object(sink, '_get_service', return_value=mock_llm_service):
            with patch.object(sink, '_get_filter_service', return_value=None):
                result = await sink.generate_response_sync(messages)
                
                assert result == "Generated response"

    @pytest.mark.asyncio
    async def test_error_handling_in_execute_action(self, sink):
        """Test error handling when executing actions on services."""
        action = SendMessageAction(
            handler_name="test",
            metadata={},
            channel_id="test_channel",
            content="Hello world"
        )
        
        # Mock service that raises an exception
        mock_service = AsyncMock()
        mock_service.send_message.side_effect = Exception("Service error")
        
        with pytest.raises(Exception, match="Service error"):
            await sink._execute_action_on_service(mock_service, action)

    @pytest.mark.asyncio
    async def test_get_filter_service_success(self, sink):
        """Test successful filter service retrieval."""
        mock_filter_service = AsyncMock()
        sink.service_registry.get_service.return_value = mock_filter_service
        
        result = await sink._get_filter_service()
        
        assert result == mock_filter_service
        sink.service_registry.get_service.assert_awaited_once_with(
            handler="llm", service_type="filter"
        )

    @pytest.mark.asyncio
    async def test_get_filter_service_failure(self, sink):
        """Test filter service retrieval failure."""
        sink.service_registry.get_service.side_effect = Exception("Service not found")
        
        result = await sink._get_filter_service()
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_filter_service_no_registry(self):
        """Test filter service when no registry is available."""
        sink = MultiServiceActionSink(service_registry=None)
        
        result = await sink._get_filter_service()
        
        assert result is None

    @pytest.mark.asyncio
    async def test_tool_result_creation_for_dict_response(self, sink, mock_tool_service):
        """Test that dict responses are converted to ToolResult objects."""
        # Mock tool service returning a dict instead of ToolResult
        mock_tool_service.execute_tool.return_value = {"raw": "dict_result"}
        
        with patch.object(sink, '_get_service', return_value=mock_tool_service):
            result = await sink.execute_tool_sync("test_tool", {"param": "value"})
            
            assert isinstance(result, ToolResult)
            assert result.tool_name == "test_tool"
            assert result.execution_status == ToolExecutionStatus.SUCCESS
            assert result.result_data == {"raw": "dict_result"}

    @pytest.mark.asyncio
    async def test_tool_result_creation_when_no_service(self, sink):
        """Test ToolResult creation when no tool service is available."""
        with patch.object(sink, '_get_service', return_value=None):
            result = await sink.execute_tool_sync("test_tool", {"param": "value"})
            
            assert isinstance(result, ToolResult)
            assert result.tool_name == "unknown"
            assert result.execution_status == ToolExecutionStatus.NOT_FOUND
            assert result.error_message == "No tool service available"

    @pytest.mark.asyncio
    async def test_process_action_with_validation_failure(self, sink):
        """Test that invalid actions don't get processed."""
        invalid_action = SendMessageAction(
            handler_name="test",
            metadata={},
            channel_id="",  # Invalid - empty channel_id
            content="Hello world"
        )
        
        with patch.object(sink, '_execute_action_on_service') as mock_execute:
            await sink._process_action(invalid_action)
            
            # Should not call execute since validation failed
            mock_execute.assert_not_called()