"""
Comprehensive tests for the refactored API adapter.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
import json
from datetime import datetime, timezone

from ciris_engine.adapters.api.api_adapter import APIAdapter
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage, FetchedMessage
from ciris_engine.schemas.correlation_schemas_v1 import ServiceCorrelation


@pytest.fixture
def mock_bus_manager():
    """Mock multi-service sink."""
    sink = AsyncMock()
    return sink


@pytest.fixture
def mock_service_registry():
    """Mock service registry."""
    registry = AsyncMock()
    
    # Create mock providers with proper async methods
    mock_provider1 = Mock()
    mock_provider1.is_healthy = AsyncMock(return_value=True)
    mock_provider1.get_capabilities = Mock(return_value=["cap1"])
    
    mock_provider2 = Mock()
    mock_provider2.is_healthy = AsyncMock(return_value=True)
    mock_provider2.get_capabilities = Mock(return_value=["cap2"])
    
    registry.get_all_services.return_value = {
        "communication": [mock_provider1],
        "tool": [mock_provider2]
    }
    return registry


@pytest.fixture
def mock_runtime_control():
    """Mock runtime control service."""
    control = AsyncMock()
    control.get_runtime_status.return_value = {"status": "running"}
    control.execute_command.return_value = {"success": True}
    return control


@pytest.fixture
def mock_telemetry_collector():
    """Mock telemetry collector."""
    collector = AsyncMock()
    collector.get_current_metrics.return_value = {"metrics": {}}
    collector.generate_report.return_value = {"report": "test"}
    return collector


@pytest.fixture
def api_adapter(mock_bus_manager, mock_service_registry, 
                mock_runtime_control, mock_telemetry_collector):
    """Create API adapter instance with mocked dependencies."""
    adapter = APIAdapter(
        host="127.0.0.1",
        port=8000,
        bus_manager=mock_bus_manager,
        service_registry=mock_service_registry,
        runtime_control=mock_runtime_control,
        telemetry_collector=mock_telemetry_collector
    )
    return adapter


@pytest.mark.asyncio
class TestAPIAdapter:
    """Test cases for API adapter."""

    async def test_init(self, api_adapter):
        """Test adapter initialization."""
        assert api_adapter.host == "127.0.0.1"
        assert api_adapter.port == 8000
        assert api_adapter.bus_manager is not None
        assert api_adapter.service_registry is not None
        assert api_adapter.runtime_control is not None
        assert api_adapter.telemetry_collector is not None
        assert len(api_adapter._message_queue) == 0

    async def test_send_message_success(self, api_adapter):
        """Test successful message sending."""
        with patch('ciris_engine.adapters.api.api_adapter.add_correlation') as mock_persist:
            result = await api_adapter.send_message("test_channel", "test message")
            
            assert result is True
            mock_persist.assert_called_once()
            # Verify correlation was logged
            call_args = mock_persist.call_args[0][0]
            assert call_args.service_type == "api"
            assert call_args.action_type == "send_message"

    async def test_send_message_failure(self, api_adapter):
        """Test message sending failure."""
        with patch('ciris_engine.adapters.api.api_adapter.add_correlation', side_effect=Exception("Test error")):
            result = await api_adapter.send_message("test_channel", "test message")
            assert result is False

    async def test_fetch_messages(self, api_adapter):
        """Test message fetching."""
        # Add a test message to the queue
        test_msg = IncomingMessage(
            message_id="test_id",
            author_id="test_author",
            author_name="Test Author",
            content="test content",
            destination_id="test_channel",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        async with api_adapter._queue_lock:
            api_adapter._message_queue.append(test_msg)
        
        # Fetch messages
        messages = await api_adapter.fetch_messages("test_channel", 10)
        
        assert len(messages) == 1
        assert messages[0].message_id == "test_id"
        assert messages[0].content == "test content"

    async def test_fetch_messages_empty(self, api_adapter):
        """Test fetching messages from empty queue."""
        messages = await api_adapter.fetch_messages("test_channel", 10)
        assert len(messages) == 0

    async def test_fetch_messages_limit(self, api_adapter):
        """Test message fetching with limit."""
        # Add multiple messages
        for i in range(5):
            test_msg = IncomingMessage(
                message_id=f"test_id_{i}",
                author_id="test_author",
                author_name="Test Author",
                content=f"test content {i}",
                destination_id="test_channel",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            async with api_adapter._queue_lock:
                api_adapter._message_queue.append(test_msg)
        
        # Fetch with limit
        messages = await api_adapter.fetch_messages("test_channel", 3)
        
        assert len(messages) == 3
        # Should get the last 3 messages
        assert messages[0].message_id == "test_id_2"
        assert messages[2].message_id == "test_id_4"

    async def test_handle_send_message_success(self, api_adapter):
        """Test handling incoming message via HTTP."""
        # Create mock request
        request_data = {
            "message_id": "test_msg_id",
            "author_id": "user123",
            "author_name": "Test User",
            "content": "Hello, world!",
            "channel_id": "general"
        }
        
        # Mock request
        request = Mock()
        request.json = AsyncMock(return_value=request_data)
        
        # Call handler
        response = await api_adapter._handle_send_message(request)
        
        # Verify response
        assert response.status == 202
        response_data = json.loads(response.text)
        assert response_data["status"] == "accepted"
        assert response_data["message_id"] == "test_msg_id"
        
        # Verify message was added to queue
        assert len(api_adapter._message_queue) == 1
        queued_msg = api_adapter._message_queue[0]
        assert queued_msg.message_id == "test_msg_id"
        assert queued_msg.content == "Hello, world!"
        
        # Verify multi-service sink was called
        # api_adapter.bus_manager.observe_message.assert_called_once()  # TODO: Update for new observer pattern

    async def test_handle_send_message_missing_fields(self, api_adapter):
        """Test handling message with missing required fields."""
        request_data = {
            "message_id": "test_msg_id",
            # Missing other required fields
        }
        
        request = Mock()
        request.json = AsyncMock(return_value=request_data)
        
        response = await api_adapter._handle_send_message(request)
        
        assert response.status == 400
        response_data = json.loads(response.text)
        assert "error" in response_data
        assert "Missing required fields" in response_data["error"]

    async def test_handle_send_message_exception(self, api_adapter):
        """Test handling message with exception."""
        request = Mock()
        request.json = AsyncMock(side_effect=Exception("JSON parse error"))
        
        response = await api_adapter._handle_send_message(request)
        
        assert response.status == 500
        response_data = json.loads(response.text)
        assert "error" in response_data

    async def test_handle_fetch_messages(self, api_adapter):
        """Test handling fetch messages request."""
        # Add test message
        test_msg = IncomingMessage(
            message_id="test_id",
            author_id="test_author",
            author_name="Test Author",
            content="test content",
            destination_id="test_channel",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        async with api_adapter._queue_lock:
            api_adapter._message_queue.append(test_msg)
        
        # Mock request
        request = Mock()
        request.match_info = {"channel_id": "test_channel"}
        request.query = {"limit": "5"}
        
        response = await api_adapter._handle_fetch_messages(request)
        
        assert response.status == 200
        response_data = json.loads(response.text)
        assert response_data["channel_id"] == "test_channel"
        assert len(response_data["messages"]) == 1
        assert response_data["messages"][0]["message_id"] == "test_id"

    async def test_handle_health_check(self, api_adapter):
        """Test health check endpoint."""
        request = Mock()
        
        response = await api_adapter._handle_health_check(request)
        
        assert response.status == 200
        response_data = json.loads(response.text)
        assert response_data["status"] == "healthy"
        assert "timestamp" in response_data
        assert "services" in response_data

    async def test_handle_health_check_service_error(self, api_adapter):
        """Test health check with service registry error."""
        api_adapter.service_registry.get_all_services.side_effect = Exception("Service error")
        
        request = Mock()
        response = await api_adapter._handle_health_check(request)
        
        assert response.status == 200
        response_data = json.loads(response.text)
        assert "services_error" in response_data

    async def test_handle_list_services(self, api_adapter):
        """Test listing services endpoint."""
        request = Mock()
        
        response = await api_adapter._handle_list_services(request)
        
        assert response.status == 200
        response_data = json.loads(response.text)
        assert "services" in response_data
        assert "timestamp" in response_data
        
        # Verify service registry was called
        api_adapter.service_registry.get_all_services.assert_called_once()

    async def test_handle_list_services_no_registry(self, api_adapter):
        """Test listing services without service registry."""
        api_adapter.service_registry = None
        
        request = Mock()
        response = await api_adapter._handle_list_services(request)
        
        assert response.status == 503
        response_data = json.loads(response.text)
        assert "Service registry not available" in response_data["error"]

    async def test_handle_runtime_status(self, api_adapter):
        """Test runtime status endpoint."""
        request = Mock()
        
        response = await api_adapter._handle_runtime_status(request)
        
        assert response.status == 200
        
        # Verify runtime control was called
        api_adapter.runtime_control.get_runtime_status.assert_called_once()

    async def test_handle_runtime_status_no_control(self, api_adapter):
        """Test runtime status without runtime control."""
        api_adapter.runtime_control = None
        
        request = Mock()
        response = await api_adapter._handle_runtime_status(request)
        
        assert response.status == 503
        response_data = json.loads(response.text)
        assert "Runtime control not available" in response_data["error"]

    async def test_handle_runtime_control(self, api_adapter):
        """Test runtime control endpoint."""
        request_data = {
            "command": "restart",
            "params": {"force": True}
        }
        
        request = Mock()
        request.json = AsyncMock(return_value=request_data)
        
        response = await api_adapter._handle_runtime_control(request)
        
        assert response.status == 200
        
        # Verify runtime control was called with correct params
        api_adapter.runtime_control.execute_command.assert_called_once_with(
            "restart", {"force": True}
        )

    async def test_handle_runtime_control_missing_command(self, api_adapter):
        """Test runtime control without command."""
        request_data: schemas.BaseSchema = {"params": {}}
        
        request = Mock()
        request.json = AsyncMock(return_value=request_data)
        
        response = await api_adapter._handle_runtime_control(request)
        
        assert response.status == 400
        response_data = json.loads(response.text)
        assert "Missing command" in response_data["error"]

    async def test_handle_metrics(self, api_adapter):
        """Test metrics endpoint."""
        request = Mock()
        
        response = await api_adapter._handle_metrics(request)
        
        assert response.status == 200
        
        # Verify telemetry collector was called
        api_adapter.telemetry_collector.get_current_metrics.assert_called_once()

    async def test_handle_telemetry_report(self, api_adapter):
        """Test telemetry report endpoint."""
        request = Mock()
        
        response = await api_adapter._handle_telemetry_report(request)
        
        assert response.status == 200
        
        # Verify telemetry collector was called
        api_adapter.telemetry_collector.generate_report.assert_called_once()

    async def test_start_stop_lifecycle(self, api_adapter):
        """Test adapter start/stop lifecycle."""
        # Test initial state
        assert not await api_adapter.is_healthy()
        
        # Start adapter (use mock to avoid actual server startup)
        with patch('aiohttp.web.AppRunner') as mock_runner_cls, \
             patch('aiohttp.web.TCPSite') as mock_site_cls:
            
            mock_runner = AsyncMock()
            mock_site = AsyncMock()
            mock_runner_cls.return_value = mock_runner
            mock_site_cls.return_value = mock_site
            
            await api_adapter.start()
            assert await api_adapter.is_healthy()
            assert api_adapter.runner is not None
            assert api_adapter.site is not None
            
            # Stop adapter - this will set runner and site to None
            await api_adapter.stop()
            assert not await api_adapter.is_healthy()

    async def test_get_capabilities(self, api_adapter):
        """Test getting adapter capabilities."""
        capabilities = await api_adapter.get_capabilities()
        
        expected_base = ["send_message", "fetch_messages", "health_check", "list_services"]
        for cap in expected_base:
            assert cap in capabilities
        
        # Should include runtime and telemetry capabilities
        assert "runtime_status" in capabilities
        assert "runtime_control" in capabilities
        assert "metrics" in capabilities
        assert "telemetry_report" in capabilities

    async def test_get_capabilities_minimal(self):
        """Test capabilities without optional services."""
        adapter = APIAdapter(host="127.0.0.1", port=8000)
        capabilities = await adapter.get_capabilities()
        
        expected_base = ["send_message", "fetch_messages", "health_check", "list_services"]
        for cap in expected_base:
            assert cap in capabilities
        
        # Should not include optional capabilities
        assert "runtime_status" not in capabilities
        assert "metrics" not in capabilities

    @patch('ciris_engine.adapters.api.api_adapter.add_correlation', return_value="mock-correlation-id")
    async def test_concurrent_message_handling(self, mock_add_correlation, api_adapter):
        """Test concurrent message processing."""
        # Send multiple messages concurrently
        tasks = []
        for i in range(10):
            task = asyncio.create_task(
                api_adapter.send_message(f"channel_{i}", f"message_{i}")
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(results)

    async def test_queue_thread_safety(self, api_adapter):
        """Test thread safety of message queue operations."""
        async def add_messages():
            for i in range(50):
                msg = IncomingMessage(
                    message_id=f"msg_{i}",
                    author_id="test",
                    author_name="Test",
                    content=f"content_{i}",
                    destination_id="test_channel",
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
                async with api_adapter._queue_lock:
                    api_adapter._message_queue.append(msg)
                await asyncio.sleep(0.001)  # Small delay
        
        async def fetch_messages():
            for i in range(10):
                await api_adapter.fetch_messages("test_channel", 5)
                await asyncio.sleep(0.005)  # Small delay
        
        # Run concurrently
        await asyncio.gather(
            add_messages(),
            fetch_messages()
        )
        
        # Should have messages in queue
        assert len(api_adapter._message_queue) > 0


@pytest.mark.asyncio
class TestAPIAdapterIntegration:
    """Integration tests for API adapter."""

    async def test_full_message_flow(self, api_adapter):
        """Test complete message flow from HTTP to processing."""
        # Simulate incoming HTTP request
        request_data = {
            "message_id": "integration_test",
            "author_id": "user123",
            "author_name": "Integration User",
            "content": "Integration test message",
            "channel_id": "integration_channel"
        }
        
        request = Mock()
        request.json = AsyncMock(return_value=request_data)
        
        # Handle the message
        response = await api_adapter._handle_send_message(request)
        
        # Verify successful response
        assert response.status == 202
        
        # Verify message is in queue
        assert len(api_adapter._message_queue) == 1
        
        # Verify message was queued (observer pattern changed)
        # The observer pattern no longer uses direct observe_message calls
        # Messages are queued and processed through the observer
        # TODO: Update test to verify new observer pattern behavior
        
        # Fetch the message back
        messages = await api_adapter.fetch_messages("integration_channel", 10)
        assert len(messages) == 1
        assert messages[0].message_id == "integration_test"
        assert messages[0].content == "Integration test message"

    async def test_error_handling_chain(self, api_adapter):
        """Test error handling across the adapter."""
        # Test JSON error
        request = Mock()
        request.json = AsyncMock(side_effect=Exception("JSON error"))
        response = await api_adapter._handle_send_message(request)
        assert response.status == 500
        
        # Test missing fields
        request = Mock()
        request.json = AsyncMock(return_value={"incomplete": "data"})
        response = await api_adapter._handle_send_message(request)
        assert response.status == 400
        
        # Test successful case (service errors removed since observer pattern changed)
        request = Mock()
        request.json = AsyncMock(return_value={
            "message_id": "test",
            "author_id": "test",
            "author_name": "test", 
            "content": "test"
        })
        response = await api_adapter._handle_send_message(request)
        assert response.status == 202  # Accepted