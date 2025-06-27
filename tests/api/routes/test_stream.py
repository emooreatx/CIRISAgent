"""
Unit tests for WebSocket streaming endpoints.

Tests WebSocket connections, authentication, message framing, and multiplexing.
"""
import pytest
import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Dict, Any, Optional

from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from ciris_engine.api.routes.stream import (
    router, 
    manager,
    StreamMessageType,
    StreamMessage,
    MessageStreamData,
    TelemetryStreamData,
    ReasoningStreamData,
    LogStreamData,
    broadcast_message,
    broadcast_telemetry,
    broadcast_reasoning,
    broadcast_log
)
from ciris_engine.schemas.api.auth import UserRole, AuthContext, APIKeyInfo
from ciris_engine.api.services.auth_service import APIAuthService


# Create test app
app = FastAPI()
app.include_router(router)


class MockAuthService:
    """Mock authentication service for testing."""
    
    def __init__(self):
        self.valid_keys = {
            "observer_key": APIKeyInfo(
                key_id="obs_123",
                role=UserRole.OBSERVER,
                expires_at=None,
                description="Test observer key",
                created_at=datetime.now(timezone.utc),
                created_by="observer_user",  # This will be used as user_id
                last_used=None,
                is_active=True
            ),
            "admin_key": APIKeyInfo(
                key_id="adm_456",
                role=UserRole.ADMIN,
                expires_at=None,
                description="Test admin key",
                created_at=datetime.now(timezone.utc),
                created_by="admin_user",  # This will be used as user_id
                last_used=None,
                is_active=True
            ),
            "authority_key": APIKeyInfo(
                key_id="auth_789",
                role=UserRole.AUTHORITY,
                expires_at=None,
                description="Test authority key",
                created_at=datetime.now(timezone.utc),
                created_by="authority_user",  # This will be used as user_id
                last_used=None,
                is_active=True
            )
        }
    
    async def validate_api_key(self, key: str) -> Optional[APIKeyInfo]:
        """Validate API key."""
        return self.valid_keys.get(key)


@pytest.fixture
def mock_auth_service():
    """Create mock auth service."""
    return MockAuthService()


@pytest.fixture
def test_client(mock_auth_service):
    """Create test client with mocked auth."""
    app.state.auth_service = mock_auth_service
    return TestClient(app)


class TestMessageStream:
    """Test suite for message streaming endpoint."""
    
    def test_message_stream_without_auth(self, test_client):
        """Test that message stream requires authentication."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect("/stream/messages") as websocket:
                # Should close immediately with auth error
                websocket.receive_json()
        assert exc_info.value.code == 1008
    
    def test_message_stream_with_valid_auth(self, test_client):
        """Test message stream with valid authentication."""
        with test_client.websocket_connect("/stream/messages?token=observer_key") as websocket:
            # Should receive auth confirmation
            data = websocket.receive_json()
            assert data["type"] == "auth"
            assert data["data"]["authenticated"] is True
            assert data["data"]["user_id"] == "observer_user"
            assert data["data"]["role"] == "OBSERVER"
            
            # Send heartbeat check
            websocket.send_json({"type": "heartbeat"})
            
            # Clean disconnect
            websocket.close()
    
    def test_message_stream_invalid_auth(self, test_client):
        """Test message stream with invalid authentication."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect("/stream/messages?token=invalid_key") as websocket:
                # Should close with auth error
                websocket.receive_json()
        assert exc_info.value.code == 1008
    
    @pytest.mark.asyncio
    async def test_broadcast_message(self):
        """Test broadcasting messages to connected clients."""
        # Reset manager state
        manager.active_connections.clear()
        manager.subscriptions.clear()
        manager.auth_contexts.clear()
        
        # Create mock websocket
        mock_ws = AsyncMock(spec=WebSocket)
        mock_ws.send_json = AsyncMock()
        
        # Connect a client
        client_id = "test_client_1"
        auth_context = AuthContext(
            user_id="test_user",
            role=UserRole.OBSERVER,
            permissions=set(),
            api_key_id="test_key",
            authenticated_at=datetime.now(timezone.utc)
        )
        
        await manager.connect(client_id, mock_ws, auth_context)
        manager.subscribe(client_id, [StreamMessageType.MESSAGE])
        
        # Broadcast a message
        message_data = MessageStreamData(
            message_id="msg_123",
            channel_id="test_channel",
            author_id="agent",
            content="Hello from agent",
            direction="outgoing"
        )
        await broadcast_message(message_data)
        
        # Verify message was sent
        calls = mock_ws.send_json.call_args_list
        assert len(calls) >= 1  # At least the broadcast
        
        # Check broadcast message (might be first or after auth)
        broadcast_found = False
        for call in calls:
            sent_data = call[0][0]
            if sent_data["type"] == "message":
                assert sent_data["data"]["message_id"] == "msg_123"
                assert sent_data["data"]["content"] == "Hello from agent"
                broadcast_found = True
                break
        assert broadcast_found, "Broadcast message not found"


class TestTelemetryStream:
    """Test suite for telemetry streaming endpoint."""
    
    def test_telemetry_stream_with_auth(self, test_client):
        """Test telemetry stream with authentication."""
        with test_client.websocket_connect("/stream/telemetry?token=observer_key") as websocket:
            # Should receive auth confirmation
            data = websocket.receive_json()
            assert data["type"] == "auth"
            assert data["data"]["authenticated"] is True
            
            # Clean disconnect
            websocket.close()
    
    @pytest.mark.asyncio
    async def test_broadcast_telemetry(self):
        """Test broadcasting telemetry to connected clients."""
        # Reset manager state
        manager.active_connections.clear()
        manager.subscriptions.clear()
        manager.auth_contexts.clear()
        
        # Create mock websocket
        mock_ws = AsyncMock(spec=WebSocket)
        mock_ws.send_json = AsyncMock()
        
        # Connect a client
        client_id = "test_telemetry_client"
        auth_context = AuthContext(
            user_id="test_user",
            role=UserRole.OBSERVER,
            permissions=set(),
            api_key_id="test_key",
            authenticated_at=datetime.now(timezone.utc)
        )
        
        await manager.connect(client_id, mock_ws, auth_context)
        manager.subscribe(client_id, [StreamMessageType.TELEMETRY])
        
        # Broadcast telemetry
        telemetry_data = TelemetryStreamData(
            metric_name="messages_processed",
            value=42.0,
            unit="count",
            tags={"handler": "observe"}
        )
        await broadcast_telemetry(telemetry_data)
        
        # Verify telemetry was sent
        calls = mock_ws.send_json.call_args_list
        assert len(calls) >= 1  # At least the broadcast
        
        # Check telemetry message
        telemetry_found = False
        for call in calls:
            sent_data = call[0][0]
            if sent_data["type"] == "telemetry":
                assert sent_data["data"]["metric_name"] == "messages_processed"
                assert sent_data["data"]["value"] == 42.0
                telemetry_found = True
                break
        assert telemetry_found, "Telemetry message not found"


class TestReasoningStream:
    """Test suite for reasoning streaming endpoint."""
    
    def test_reasoning_stream_with_auth(self, test_client):
        """Test reasoning stream with authentication."""
        with test_client.websocket_connect("/stream/reasoning?token=observer_key") as websocket:
            # Should receive auth confirmation
            data = websocket.receive_json()
            assert data["type"] == "auth"
            assert data["data"]["authenticated"] is True
            
            # Clean disconnect
            websocket.close()
    
    @pytest.mark.asyncio
    async def test_broadcast_reasoning(self):
        """Test broadcasting reasoning traces to connected clients."""
        # Reset manager state
        manager.active_connections.clear()
        manager.subscriptions.clear()
        manager.auth_contexts.clear()
        
        # Create mock websocket
        mock_ws = AsyncMock(spec=WebSocket)
        mock_ws.send_json = AsyncMock()
        
        # Connect a client
        client_id = "test_reasoning_client"
        auth_context = AuthContext(
            user_id="test_user",
            role=UserRole.OBSERVER,
            permissions=set(),
            api_key_id="test_key",
            authenticated_at=datetime.now(timezone.utc)
        )
        
        await manager.connect(client_id, mock_ws, auth_context)
        manager.subscribe(client_id, [StreamMessageType.REASONING])
        
        # Broadcast reasoning
        reasoning_data = ReasoningStreamData(
            reasoning_id="reason_123",
            step="analyze_message",
            thought="User is asking about the weather",
            depth=1,
            handler="observe"
        )
        await broadcast_reasoning(reasoning_data)
        
        # Verify reasoning was sent
        calls = mock_ws.send_json.call_args_list
        assert len(calls) >= 1  # At least the broadcast
        
        # Check reasoning message
        reasoning_found = False
        for call in calls:
            sent_data = call[0][0]
            if sent_data["type"] == "reasoning":
                assert sent_data["data"]["reasoning_id"] == "reason_123"
                assert sent_data["data"]["thought"] == "User is asking about the weather"
                reasoning_found = True
                break
        assert reasoning_found, "Reasoning message not found"


class TestLogStream:
    """Test suite for log streaming endpoint."""
    
    def test_log_stream_requires_admin(self, test_client):
        """Test that log stream requires admin role."""
        # Try with observer role
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect("/stream/logs?token=observer_key") as websocket:
                # Should close with permission error
                websocket.receive_json()
        assert exc_info.value.code == 1008
    
    def test_log_stream_with_admin_auth(self, test_client):
        """Test log stream with admin authentication."""
        with test_client.websocket_connect("/stream/logs?token=admin_key") as websocket:
            # Should receive auth confirmation
            data = websocket.receive_json()
            assert data["type"] == "auth"
            assert data["data"]["authenticated"] is True
            assert data["data"]["role"] == "ADMIN"
            
            # Clean disconnect
            websocket.close()
    
    @pytest.mark.asyncio
    async def test_broadcast_log_permission_check(self):
        """Test that log broadcasts respect role permissions."""
        # Reset manager state
        manager.active_connections.clear()
        manager.subscriptions.clear()
        manager.auth_contexts.clear()
        
        # Create mock websockets
        mock_ws_observer = AsyncMock(spec=WebSocket)
        mock_ws_observer.send_json = AsyncMock()
        
        mock_ws_admin = AsyncMock(spec=WebSocket)
        mock_ws_admin.send_json = AsyncMock()
        
        # Connect observer client
        observer_id = "observer_client"
        observer_auth = AuthContext(
            user_id="observer_user",
            role=UserRole.OBSERVER,
            permissions=set(),
            api_key_id="obs_key",
            authenticated_at=datetime.now(timezone.utc)
        )
        await manager.connect(observer_id, mock_ws_observer, observer_auth)
        manager.subscribe(observer_id, [StreamMessageType.LOG])
        
        # Connect admin client
        admin_id = "admin_client"
        admin_auth = AuthContext(
            user_id="admin_user",
            role=UserRole.ADMIN,
            permissions=set(),
            api_key_id="admin_key",
            authenticated_at=datetime.now(timezone.utc)
        )
        await manager.connect(admin_id, mock_ws_admin, admin_auth)
        manager.subscribe(admin_id, [StreamMessageType.LOG])
        
        # Broadcast log
        log_data = LogStreamData(
            level="ERROR",
            logger_name="ciris_engine.core",
            message="Test error message",
            context={"module": "test"}
        )
        await broadcast_log(log_data, min_role=UserRole.ADMIN)
        
        # Verify only admin received the log
        # Observer should not have log message
        observer_calls = mock_ws_observer.send_json.call_args_list
        observer_has_log = any(call[0][0]["type"] == "log" for call in observer_calls)
        assert not observer_has_log, "Observer should not receive log messages"
        
        # Admin should have log message
        admin_calls = mock_ws_admin.send_json.call_args_list
        admin_has_log = any(call[0][0]["type"] == "log" for call in admin_calls)
        assert admin_has_log, "Admin should receive log messages"
        
        # Verify log content
        for call in admin_calls:
            if call[0][0]["type"] == "log":
                assert call[0][0]["data"]["message"] == "Test error message"
                break


class TestMultiplexedStream:
    """Test suite for multiplexed streaming endpoint."""
    
    def test_multiplexed_stream_subscription(self, test_client):
        """Test multiplexed stream with subscription management."""
        with test_client.websocket_connect("/stream/all?token=admin_key") as websocket:
            # Should receive auth confirmation
            data = websocket.receive_json()
            assert data["type"] == "auth"
            assert data["data"]["authenticated"] is True
            
            # Send subscription request
            websocket.send_json({
                "type": "subscribe",
                "streams": ["message", "telemetry", "log"]
            })
            
            # Should receive subscription confirmation
            data = websocket.receive_json()
            assert data["type"] == "subscribe"
            assert set(data["data"]["subscribed"]) == {"message", "telemetry", "log"}
            assert data["data"]["denied"] == []
            
            # Test unsubscribe
            websocket.send_json({
                "type": "unsubscribe",
                "streams": ["telemetry"]
            })
            
            data = websocket.receive_json()
            assert data["type"] == "unsubscribe"
            assert data["data"]["removed"] == ["telemetry"]
            
            # Clean disconnect
            websocket.close()
    
    def test_multiplexed_stream_permission_filtering(self, test_client):
        """Test that multiplexed stream filters based on permissions."""
        with test_client.websocket_connect("/stream/all?token=observer_key") as websocket:
            # Should receive auth confirmation
            data = websocket.receive_json()
            assert data["type"] == "auth"
            assert data["data"]["role"] == "OBSERVER"
            
            # Try to subscribe to all streams including logs
            websocket.send_json({
                "type": "subscribe",
                "streams": ["message", "telemetry", "reasoning", "log"]
            })
            
            # Should receive subscription confirmation without log
            data = websocket.receive_json()
            assert data["type"] == "subscribe"
            assert "log" not in data["data"]["subscribed"]
            assert "log" in data["data"]["denied"]
            
            # Clean disconnect
            websocket.close()
    
    def test_multiplexed_requires_initial_subscription(self, test_client):
        """Test that multiplexed stream requires initial subscription."""
        with test_client.websocket_connect("/stream/all?token=observer_key") as websocket:
            # Should receive auth confirmation
            data = websocket.receive_json()
            assert data["type"] == "auth"
            
            # Send non-subscription message first
            websocket.send_json({
                "type": "random",
                "data": "test"
            })
            
            # Should receive error
            data = websocket.receive_json()
            assert data["type"] == "error"
            assert "subscription request" in data["data"]["message"]
            
            # Connection should close after error
            websocket.close()


class TestConnectionManager:
    """Test suite for connection manager functionality."""
    
    @pytest.mark.asyncio
    async def test_connection_lifecycle(self):
        """Test connection manager lifecycle."""
        # Reset manager state
        manager.active_connections.clear()
        manager.subscriptions.clear()
        manager.auth_contexts.clear()
        
        # Create mock websocket
        mock_ws = AsyncMock(spec=WebSocket)
        mock_ws.send_json = AsyncMock()
        
        client_id = "test_lifecycle"
        auth_context = AuthContext(
            user_id="test_user",
            role=UserRole.OBSERVER,
            permissions=set(),
            api_key_id="test_key",
            authenticated_at=datetime.now(timezone.utc)
        )
        
        # Test connect
        await manager.connect(client_id, mock_ws, auth_context)
        assert client_id in manager.active_connections
        assert client_id in manager.subscriptions
        assert client_id in manager.auth_contexts
        
        # Test subscribe
        manager.subscribe(client_id, [StreamMessageType.MESSAGE, StreamMessageType.TELEMETRY])
        assert StreamMessageType.MESSAGE in manager.subscriptions[client_id]
        assert StreamMessageType.TELEMETRY in manager.subscriptions[client_id]
        
        # Test unsubscribe
        manager.unsubscribe(client_id, [StreamMessageType.TELEMETRY])
        assert StreamMessageType.MESSAGE in manager.subscriptions[client_id]
        assert StreamMessageType.TELEMETRY not in manager.subscriptions[client_id]
        
        # Test disconnect
        manager.disconnect(client_id)
        assert client_id not in manager.active_connections
        assert client_id not in manager.subscriptions
        assert client_id not in manager.auth_contexts
    
    @pytest.mark.asyncio
    async def test_broadcast_filtering(self):
        """Test that broadcasts are filtered by subscription."""
        # Reset manager state
        manager.active_connections.clear()
        manager.subscriptions.clear()
        manager.auth_contexts.clear()
        
        # Create mock websockets
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws1.send_json = AsyncMock()
        
        mock_ws2 = AsyncMock(spec=WebSocket)
        mock_ws2.send_json = AsyncMock()
        
        # Connect two clients with different subscriptions
        client1_id = "client_messages"
        await manager.connect(client1_id, mock_ws1, None)
        manager.subscribe(client1_id, [StreamMessageType.MESSAGE])
        
        client2_id = "client_telemetry"
        await manager.connect(client2_id, mock_ws2, None)
        manager.subscribe(client2_id, [StreamMessageType.TELEMETRY])
        
        # Broadcast a message
        message = StreamMessage(
            type=StreamMessageType.MESSAGE,
            data={"content": "test message"}
        )
        await manager.broadcast(message, StreamMessageType.MESSAGE)
        
        # Only client1 should receive it
        assert mock_ws1.send_json.call_count >= 1
        assert mock_ws2.send_json.call_count == 0
        
        # Reset calls
        mock_ws1.send_json.reset_mock()
        mock_ws2.send_json.reset_mock()
        
        # Broadcast telemetry
        telemetry = StreamMessage(
            type=StreamMessageType.TELEMETRY,
            data={"metric": "test"}
        )
        await manager.broadcast(telemetry, StreamMessageType.TELEMETRY)
        
        # Only client2 should receive it
        mock_ws1.send_json.assert_not_called()
        mock_ws2.send_json.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_handling_on_send(self):
        """Test that connection manager handles send errors gracefully."""
        # Reset manager state
        manager.active_connections.clear()
        manager.subscriptions.clear()
        manager.auth_contexts.clear()
        
        # Create mock websocket that fails on send
        mock_ws = AsyncMock(spec=WebSocket)
        mock_ws.send_json = AsyncMock(side_effect=Exception("Connection lost"))
        
        client_id = "failing_client"
        await manager.connect(client_id, mock_ws, None)
        manager.subscribe(client_id, [StreamMessageType.MESSAGE])
        
        # Broadcast should not raise exception
        message = StreamMessage(
            type=StreamMessageType.MESSAGE,
            data={"content": "test"}
        )
        await manager.broadcast(message, StreamMessageType.MESSAGE)
        
        # Client should be disconnected
        assert client_id not in manager.active_connections