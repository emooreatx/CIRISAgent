"""
Tests for consolidated system management endpoints.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, MagicMock
from fastapi.testclient import TestClient

from ciris_engine.api.app import create_app
from ciris_engine.schemas.api.auth import UserRole, AuthContext
from ciris_engine.schemas.services.resources_core import (
    ResourceSnapshot, ResourceBudget, ResourceLimit, ResourceAction
)


@pytest.fixture
def mock_services():
    """Create mock services for testing."""
    # Mock time service
    time_service = Mock()
    time_service.now = Mock(return_value=datetime.now(timezone.utc))
    time_service._start_time = datetime.now(timezone.utc) - timedelta(hours=1)
    time_service._mock_time = None
    time_service._last_sync = datetime.now(timezone.utc)
    
    # Mock resource monitor
    resource_monitor = Mock()
    resource_monitor.snapshot = ResourceSnapshot(
        memory_mb=512,
        memory_percent=50,
        cpu_percent=25,
        cpu_average_1m=20,
        tokens_used_hour=1000,
        tokens_used_day=5000,
        thoughts_active=3,
        thoughts_queued=2,
        disk_used_mb=100,
        disk_free_mb=900,
        healthy=True,
        warnings=["memory_mb: approaching limit"],
        critical=[]
    )
    resource_monitor.budget = ResourceBudget(
        memory_mb=ResourceLimit(limit=1024, warning=768, critical=900, action=ResourceAction.WARN),
        cpu_percent=ResourceLimit(limit=100, warning=80, critical=95, action=ResourceAction.DEFER),
        tokens_hour=ResourceLimit(limit=10000, warning=8000, critical=9500, action=ResourceAction.WARN),
        tokens_day=ResourceLimit(limit=100000, warning=80000, critical=95000, action=ResourceAction.DEFER),
        disk_mb=ResourceLimit(limit=1000, warning=800, critical=950, action=ResourceAction.WARN),
        thoughts_active=ResourceLimit(limit=10, warning=8, critical=9, action=ResourceAction.WARN)
    )
    
    # Mock runtime control
    runtime_control = Mock()
    runtime_control.pause_processing = AsyncMock(return_value=Mock(
        success=True,
        message="Processing paused",
        processor_state="paused",
        queue_depth=5
    ))
    runtime_control.resume_processing = AsyncMock(return_value=Mock(
        success=True,
        message="Processing resumed",
        processor_state="running",
        queue_depth=5
    ))
    runtime_control.get_runtime_status = AsyncMock(return_value=Mock(
        processor_state="running",
        cognitive_state="WORK",
        queue_status=Mock(pending_thoughts=3, pending_tasks=2)
    ))
    
    # Mock shutdown service
    shutdown_service = Mock()
    shutdown_service.is_shutdown_requested = Mock(return_value=False)
    shutdown_service.get_shutdown_reason = Mock(return_value=None)
    shutdown_service.request_shutdown = AsyncMock(return_value=None)
    
    # Mock service registry
    service_registry = Mock()
    service_registry.get_services_by_type = Mock(return_value=[])
    
    # Mock runtime with agent processor
    runtime = Mock()
    runtime.agent_processor = Mock()
    runtime.agent_processor.get_current_state = Mock(return_value="WORK")
    runtime.shutdown_service = shutdown_service
    
    # Mock initialization service
    init_service = Mock()
    init_service.is_initialized = Mock(return_value=True)
    
    return {
        'time_service': time_service,
        'resource_monitor': resource_monitor,
        'runtime_control': runtime_control,
        'shutdown_service': shutdown_service,
        'service_registry': service_registry,
        'runtime': runtime,
        'initialization_service': init_service
    }


@pytest.fixture
def test_app(mock_services):
    """Create test app with mocked services."""
    app = create_app()
    
    # Set up app state with mock services
    for service_name, service in mock_services.items():
        setattr(app.state, service_name, service)
    
    # Mock auth service
    mock_auth_service = Mock()
    mock_auth_service.validate_api_key = AsyncMock(return_value=Mock(
        user_id="test_user",
        role=UserRole.ADMIN
    ))
    mock_auth_service._get_key_id = Mock(return_value="test_key")
    app.state.auth_service = mock_auth_service
    
    return app


@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)


def test_system_health(client):
    """Test GET /v1/system/health endpoint."""
    response = client.get("/v1/system/health")
    assert response.status_code == 200
    
    data = response.json()["data"]
    assert data["status"] in ["healthy", "degraded", "critical", "initializing"]
    assert data["version"] == "3.0.0"
    assert data["uptime_seconds"] >= 0
    assert data["initialization_complete"] is True
    assert data["cognitive_state"] == "WORK"
    assert "timestamp" in data


def test_system_time(client):
    """Test GET /v1/system/time endpoint."""
    response = client.get("/v1/system/time")
    assert response.status_code == 200
    
    data = response.json()["data"]
    assert "system_time" in data
    assert "agent_time" in data
    assert data["uptime_seconds"] >= 0
    
    # Check time sync structure
    assert "time_sync" in data
    sync = data["time_sync"]
    assert sync["synchronized"] is True
    assert "drift_ms" in sync
    assert "last_sync" in sync
    assert sync["sync_source"] == "system"


def test_system_resources_requires_auth(client):
    """Test that /v1/system/resources requires authentication."""
    response = client.get("/v1/system/resources")
    assert response.status_code == 401


def test_system_resources_with_auth(client):
    """Test GET /v1/system/resources with authentication."""
    headers = {"Authorization": "Bearer test_token"}
    response = client.get("/v1/system/resources", headers=headers)
    assert response.status_code == 200
    
    data = response.json()["data"]
    assert "current_usage" in data
    assert "limits" in data
    assert data["health_status"] == "warning"  # Due to warning in snapshot
    assert len(data["warnings"]) == 1
    assert len(data["critical"]) == 0


def test_runtime_control_pause(client):
    """Test POST /v1/system/runtime/pause."""
    headers = {"Authorization": "Bearer test_token"}
    response = client.post(
        "/v1/system/runtime/pause",
        headers=headers,
        json={"reason": "Testing pause"}
    )
    assert response.status_code == 200
    
    data = response.json()["data"]
    assert data["success"] is True
    assert data["message"] == "Processing paused"
    assert data["processor_state"] == "paused"


def test_runtime_control_resume(client):
    """Test POST /v1/system/runtime/resume."""
    headers = {"Authorization": "Bearer test_token"}
    response = client.post(
        "/v1/system/runtime/resume",
        headers=headers,
        json={"reason": "Testing resume"}
    )
    assert response.status_code == 200
    
    data = response.json()["data"]
    assert data["success"] is True
    assert data["message"] == "Processing resumed"
    assert data["processor_state"] == "running"


def test_runtime_control_state(client):
    """Test POST /v1/system/runtime/state."""
    headers = {"Authorization": "Bearer test_token"}
    response = client.post(
        "/v1/system/runtime/state",
        headers=headers,
        json={"reason": "Check state"}
    )
    assert response.status_code == 200
    
    data = response.json()["data"]
    assert data["success"] is True
    assert data["processor_state"] == "running"
    assert data["cognitive_state"] == "WORK"
    assert data["queue_depth"] == 5


def test_runtime_control_invalid_action(client):
    """Test runtime control with invalid action."""
    headers = {"Authorization": "Bearer test_token"}
    response = client.post(
        "/v1/system/runtime/invalid",
        headers=headers,
        json={"reason": "Testing"}
    )
    assert response.status_code == 400
    assert "Invalid action" in response.json()["detail"]


def test_services_status(client, mock_services):
    """Test GET /v1/system/services."""
    # Add some mock health checks
    mock_services['time_service'].is_healthy = Mock(return_value=True)
    mock_services['resource_monitor'].is_healthy = AsyncMock(return_value=True)
    mock_services['resource_monitor'].get_status = Mock(return_value=Mock(
        metrics={"checks_performed": 100}
    ))
    
    headers = {"Authorization": "Bearer test_token"}
    response = client.get("/v1/system/services", headers=headers)
    assert response.status_code == 200
    
    data = response.json()["data"]
    assert "services" in data
    assert data["total_services"] > 0
    assert data["healthy_services"] >= 0
    assert "timestamp" in data
    
    # Verify service structure
    if data["services"]:
        service = data["services"][0]
        assert "name" in service
        assert "type" in service
        assert "healthy" in service
        assert "available" in service


def test_shutdown_without_confirmation(client):
    """Test shutdown without confirmation flag."""
    headers = {"Authorization": "Bearer test_token"}
    response = client.post(
        "/v1/system/shutdown",
        headers=headers,
        json={
            "reason": "Test shutdown",
            "confirm": False
        }
    )
    assert response.status_code == 400
    assert "Confirmation required" in response.json()["detail"]


def test_shutdown_with_confirmation(client):
    """Test proper shutdown with confirmation."""
    headers = {"Authorization": "Bearer test_token"}
    response = client.post(
        "/v1/system/shutdown",
        headers=headers,
        json={
            "reason": "Test shutdown",
            "confirm": True,
            "force": False
        }
    )
    assert response.status_code == 200
    
    data = response.json()["data"]
    assert data["status"] == "initiated"
    assert data["shutdown_initiated"] is True
    assert "Test shutdown" in data["message"]
    assert "timestamp" in data


def test_shutdown_already_requested(client, mock_services):
    """Test shutdown when already shutting down."""
    # Mock shutdown already requested
    mock_services['shutdown_service'].is_shutdown_requested = Mock(return_value=True)
    mock_services['shutdown_service'].get_shutdown_reason = Mock(
        return_value="Previous shutdown request"
    )
    
    headers = {"Authorization": "Bearer test_token"}
    response = client.post(
        "/v1/system/shutdown",
        headers=headers,
        json={
            "reason": "Another shutdown",
            "confirm": True
        }
    )
    assert response.status_code == 409
    assert "already requested" in response.json()["detail"]


def test_time_service_not_available(client, mock_services):
    """Test handling when time service is not available."""
    # Remove time service
    client.app.state.time_service = None
    
    response = client.get("/v1/system/time")
    assert response.status_code == 503
    assert "Time service not available" in response.json()["detail"]


def test_runtime_control_not_available(client):
    """Test handling when runtime control is not available."""
    # Remove runtime control
    client.app.state.runtime_control = None
    
    headers = {"Authorization": "Bearer test_token"}
    response = client.post(
        "/v1/system/runtime/pause",
        headers=headers,
        json={"reason": "Test"}
    )
    assert response.status_code == 503
    assert "Runtime control service not available" in response.json()["detail"]