"""
Comprehensive tests for agent API routes.

Tests all endpoints in /v1/agent/* to improve coverage from 20.6%.
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from ciris_engine.logic.adapters.api.app import create_app
from ciris_engine.logic.adapters.api.routes.agent import (
    AgentIdentity,
    AgentStatus,
    ConversationMessage,
    InteractRequest,
    InteractResponse,
)
from ciris_engine.schemas.api.agent import AgentLineage, ServiceAvailability


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Get auth headers for testing."""
    # Use default dev credentials
    return {"Authorization": "Bearer admin:ciris_admin_password"}


@pytest.fixture
def app_with_runtime():
    """Create app with mocked runtime."""
    app = create_app()

    # Create mock runtime
    mock_runtime = MagicMock()
    mock_runtime.is_running = True
    mock_runtime.start_time = datetime.now(timezone.utc)
    mock_runtime.processor = MagicMock()
    mock_runtime.processor.current_state = "WORK"
    mock_runtime.processor.completed_tasks = 42
    mock_runtime.communication_service = MagicMock()
    mock_runtime.memory_service = MagicMock()

    app.state.runtime = mock_runtime

    return TestClient(app), mock_runtime


class TestAgentRoutes:
    """Test agent API endpoints."""

    def test_interact_endpoint_success(self, client, auth_headers, mock_services):
        """Test successful interaction with agent."""
        # Setup mock response
        mock_services["communication"].interact.return_value = {
            "response": "Hello! How can I help you?",
            "channel_id": "api_test",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        response = client.post(
            "/v1/agent/interact", headers=auth_headers, json={"message": "Hello", "channel_id": "api_test"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "response" in data["data"]
        assert data["data"]["response"] == "Hello! How can I help you?"

    def test_interact_endpoint_no_auth(self, client):
        """Test that interact endpoint requires authentication."""
        response = client.post("/v1/agent/interact", json={"message": "Hello", "channel_id": "api_test"})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_interact_endpoint_invalid_message(self, client, auth_headers):
        """Test interact with invalid message."""
        response = client.post(
            "/v1/agent/interact", headers=auth_headers, json={"message": "", "channel_id": "api_test"}  # Empty message
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_agent_status(self, client, auth_headers, mock_services):
        """Test getting agent status."""
        # Setup mock status using actual schema
        mock_status = AgentStatus(
            agent_id="test_agent",
            name="TestBot",
            version="1.0.4-beta",
            codename="Trinity",
            code_hash="abc123",
            cognitive_state="WORK",
            uptime_seconds=3600.5,
            messages_processed=42,
            last_activity=datetime.now(timezone.utc),
            current_task="Processing test request",
            services_active=21,
            memory_usage_mb=256.7,
            multi_provider_services={"llm": 3, "memory": 2},
        )
        mock_services["runtime_control"].get_agent_status = AsyncMock(return_value=mock_status)

        response = client.get("/v1/agent/status", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["cognitive_state"] == "WORK"
        assert data["data"]["messages_processed"] == 42
        assert data["data"]["services_active"] == 21
        assert data["data"]["version"] == "1.0.4-beta"

    def test_get_agent_identity(self, client, auth_headers, mock_services):
        """Test getting agent identity."""
        # Setup mock identity using actual schema
        mock_identity = AgentIdentity(
            agent_id="test_agent",
            name="TestBot",
            purpose="Testing API endpoints",
            created_at=datetime.now(timezone.utc),
            lineage=AgentLineage(
                creator="test_creator",
                template="default",
                creation_ceremony="test_ceremony",
                ethical_framework="Covenant 1.0b",
            ),
            variance_threshold=0.15,
            tools=["speak", "observe", "memorize"],
            handlers=["ObserveHandler", "SpeakHandler"],
            services=ServiceAvailability(llm=True, memory=True, tools=True, wise_authority=False),
            permissions=["READ", "WRITE", "EXECUTE"],
        )
        mock_services["runtime_control"].get_agent_identity.return_value = mock_identity

        response = client.get("/v1/agent/identity", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["agent_id"] == "test_agent"
        assert data["data"]["name"] == "TestBot"
        assert "speak" in data["data"]["capabilities"]

    def test_get_conversation_history(self, client, auth_headers, mock_services):
        """Test getting conversation history."""
        # Setup mock history using actual schema
        mock_messages = [
            ConversationMessage(id="msg_1", role="user", content="Hello", timestamp=datetime.now(timezone.utc)),
            ConversationMessage(
                id="msg_2", role="assistant", content="Hello! How can I help?", timestamp=datetime.now(timezone.utc)
            ),
        ]
        mock_services["memory"].recall.return_value = mock_messages

        response = client.get("/v1/agent/history", headers=auth_headers, params={"channel_id": "api_test", "limit": 10})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["messages"]) == 2
        assert data["data"]["messages"][0]["content"] == "Hello"

    def test_get_history_invalid_limit(self, client, auth_headers):
        """Test history with invalid limit."""
        response = client.get("/v1/agent/history", headers=auth_headers, params={"limit": -1})  # Invalid negative limit

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_clear_conversation_history(self, client, auth_headers, mock_services):
        """Test clearing conversation history."""
        mock_services["memory"].clear_history = AsyncMock(return_value=True)

        response = client.delete("/v1/agent/history", headers=auth_headers, params={"channel_id": "api_test"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "History cleared successfully"

    def test_get_agent_metrics(self, client, auth_headers, mock_services):
        """Test getting agent metrics."""
        # Setup mock metrics
        mock_metrics = {
            "total_interactions": 1337,
            "average_response_time_ms": 250.5,
            "success_rate": 0.98,
            "active_channels": 5,
            "memory_usage_mb": 512,
            "uptime_hours": 168,
        }
        mock_services["runtime_control"].get_metrics = AsyncMock(return_value=mock_metrics)

        response = client.get("/v1/agent/metrics", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total_interactions"] == 1337
        assert data["data"]["success_rate"] == 0.98

    def test_interact_with_context(self, client, auth_headers, mock_services):
        """Test interaction with additional context."""
        mock_services["communication"].interact.return_value = {
            "response": "I understand the context",
            "channel_id": "api_test",
        }

        response = client.post(
            "/v1/agent/interact",
            headers=auth_headers,
            json={
                "message": "Continue our discussion",
                "channel_id": "api_test",
                "context": {"previous_topic": "AI ethics", "user_preference": "detailed explanations"},
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

        # Verify context was passed to service
        mock_services["communication"].interact.assert_called_once()
        call_args = mock_services["communication"].interact.call_args
        assert "context" in call_args[1] or (len(call_args[0]) > 2 and "previous_topic" in str(call_args))

    def test_status_when_shutdown(self, client, auth_headers, mock_services):
        """Test status when agent is in shutdown state."""
        mock_status = AgentStatus(
            agent_id="test_agent",
            name="TestBot",
            version="1.0.4-beta",
            codename="Trinity",
            cognitive_state="SHUTDOWN",  # Shutdown state
            uptime_seconds=7200.0,
            messages_processed=100,
            last_activity=datetime.now(timezone.utc),
            current_task="Shutting down",
            services_active=0,
            memory_usage_mb=128.0,
        )
        mock_services["runtime_control"].get_agent_status = AsyncMock(return_value=mock_status)

        response = client.get("/v1/agent/status", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["cognitive_state"] == "SHUTDOWN"
        assert data["data"]["current_task"] == "Shutting down"

    def test_interact_rate_limiting(self, client, auth_headers, mock_services):
        """Test rate limiting on interact endpoint."""
        # Note: This would require rate limiting middleware to be configured
        # For now, just test multiple rapid requests succeed
        mock_services["communication"].interact.return_value = {"response": "OK"}

        for i in range(5):
            response = client.post(
                "/v1/agent/interact", headers=auth_headers, json={"message": f"Message {i}", "channel_id": "api_test"}
            )
            assert response.status_code == status.HTTP_200_OK

    def test_history_pagination(self, client, auth_headers, mock_services):
        """Test history pagination parameters."""
        mock_services["memory"].recall.return_value = []

        response = client.get(
            "/v1/agent/history", headers=auth_headers, params={"channel_id": "api_test", "limit": 20, "offset": 10}
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify pagination params were passed
        mock_services["memory"].recall.assert_called_once()
        call_args = mock_services["memory"].recall.call_args
        # Check that limit and offset were passed somehow
        assert "limit" in str(call_args) or "20" in str(call_args)
