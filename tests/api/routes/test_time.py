"""
Unit tests for System Time API endpoint.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from ciris_engine.api.routes.system import router
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol


class MockTimeService(TimeServiceProtocol):
    """Mock implementation of TimeService for testing."""
    
    def __init__(self):
        self._running = False
        self._start_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        self._mock_time = None
        self._last_sync = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    async def start(self) -> None:
        self._running = True
    
    async def stop(self) -> None:
        self._running = False
    
    def is_healthy(self) -> bool:
        return self._running
    
    def get_status(self) -> dict:
        return {"service_name": "TimeService", "is_healthy": self._running}
    
    def get_capabilities(self) -> dict:
        return {"service_name": "TimeService", "actions": ["now", "now_iso", "timestamp"]}
    
    def now(self) -> datetime:
        if self._mock_time:
            return self._mock_time
        return datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    def now_iso(self) -> str:
        return self.now().isoformat()
    
    def timestamp(self) -> float:
        return self.now().timestamp()


@pytest.fixture
def app():
    """Create test FastAPI app with system routes."""
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    
    # Add mock time service to app state
    app.state.time_service = MockTimeService()
    
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


def test_get_system_time(client):
    """Test GET /v1/system/time endpoint."""
    response = client.get("/v1/system/time")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert "data" in data
    assert "metadata" in data
    
    # Check data fields
    time_data = data["data"]
    assert "system_time" in time_data
    assert "agent_time" in time_data
    assert "uptime_seconds" in time_data
    assert "time_sync" in time_data
    
    # Verify values
    assert time_data["agent_time"] == "2025-01-01T12:00:00+00:00"
    assert time_data["uptime_seconds"] == 43200.0  # 12 hours difference
    
    # Check time sync structure
    sync = time_data["time_sync"]
    assert "synchronized" in sync
    assert "drift_ms" in sync
    assert "last_sync" in sync
    assert "sync_source" in sync


def test_get_system_time_no_service(client):
    """Test GET /v1/system/time when service is unavailable."""
    # Remove time service
    client.app.state.time_service = None
    
    response = client.get("/v1/system/time")
    
    assert response.status_code == 503
    assert "Time service not available" in response.json()["detail"]


def test_get_system_time_includes_uptime(client):
    """Test that GET /v1/system/time includes uptime information."""
    response = client.get("/v1/system/time")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check that uptime is included
    time_data = data["data"]
    assert "uptime_seconds" in time_data
    assert time_data["uptime_seconds"] == 43200.0  # 12 hours difference


def test_get_system_time_no_start_time(client):
    """Test GET /v1/system/time when service has no start time."""
    # Remove start time
    client.app.state.time_service._start_time = None
    
    response = client.get("/v1/system/time")
    
    assert response.status_code == 200
    data = response.json()
    
    time_data = data["data"]
    assert time_data["uptime_seconds"] == 0.0


def test_get_system_time_sync_info(client):
    """Test that GET /v1/system/time includes sync information."""
    response = client.get("/v1/system/time")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check time sync fields
    time_data = data["data"]
    sync_data = time_data["time_sync"]
    assert "synchronized" in sync_data
    assert "sync_source" in sync_data
    assert "last_sync" in sync_data
    assert "drift_ms" in sync_data
    
    # Verify sync source is system when not mocked
    assert sync_data["sync_source"] == "system"
    assert sync_data["last_sync"] == "2025-01-01T00:00:00+00:00"
    # Note: synchronized status depends on actual drift between system and agent time


def test_get_system_time_mocked(client):
    """Test GET /v1/system/time when time is mocked."""
    # Set mock time
    mock_time = datetime(2025, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
    client.app.state.time_service._mock_time = mock_time
    
    response = client.get("/v1/system/time")
    
    assert response.status_code == 200
    data = response.json()
    
    time_data = data["data"]
    sync_data = time_data["time_sync"]
    assert sync_data["synchronized"] is False
    assert sync_data["sync_source"] == "mock"


def test_system_time_error_handling(client):
    """Test error handling when time service raises exception."""
    # Mock time service to raise exception
    mock_service = Mock(spec=TimeServiceProtocol)
    mock_service.now.side_effect = Exception("Time service error")
    
    client.app.state.time_service = mock_service
    
    # Test system time endpoint
    response = client.get("/v1/system/time")
    assert response.status_code == 500
    assert "Failed to get time information" in response.json()["detail"]


def test_metadata_in_response(client):
    """Test that response includes proper metadata."""
    response = client.get("/v1/system/time")
    assert response.status_code == 200
    
    data = response.json()
    assert "metadata" in data
    
    metadata = data["metadata"]
    assert "timestamp" in metadata
    assert "request_id" in metadata
    assert "duration_ms" in metadata


def test_system_time_consolidated_info(client):
    """Test that system time endpoint returns all consolidated information."""
    response = client.get("/v1/system/time")
    
    assert response.status_code == 200
    data = response.json()
    
    time_data = data["data"]
    
    # Check all required fields are present
    assert "system_time" in time_data  # Host OS time
    assert "agent_time" in time_data   # TimeService time
    assert "uptime_seconds" in time_data
    assert "time_sync" in time_data
    
    # Verify system_time is a valid timestamp
    assert time_data["system_time"] is not None
    
    # Verify time_sync has all required fields
    sync = time_data["time_sync"]
    assert isinstance(sync, dict)
    assert "synchronized" in sync
    assert "drift_ms" in sync
    assert "last_sync" in sync
    assert "sync_source" in sync


def test_system_time_drift_calculation(client):
    """Test that drift is calculated correctly between system and agent time."""
    # Set a different mock time to create drift
    mock_time = datetime(2025, 1, 1, 12, 30, 0, tzinfo=timezone.utc)  # 30 minutes ahead
    client.app.state.time_service._mock_time = mock_time
    
    response = client.get("/v1/system/time")
    
    assert response.status_code == 200
    data = response.json()
    
    time_data = data["data"]
    sync_data = time_data["time_sync"]
    
    # Should show drift and not synchronized
    assert sync_data["synchronized"] is False
    assert sync_data["drift_ms"] != 0  # Should have some drift
    assert sync_data["sync_source"] == "mock"