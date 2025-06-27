"""
Unit tests for Time Service API routes.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from ciris_engine.api.routes.time import router
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
    """Create test FastAPI app with time routes."""
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    
    # Add mock time service to app state
    app.state.time_service = MockTimeService()
    
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


def test_get_current_time(client):
    """Test GET /v1/time/current endpoint."""
    response = client.get("/v1/time/current")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert "data" in data
    assert "metadata" in data
    
    # Check data fields
    time_data = data["data"]
    assert "current_time" in time_data
    assert "current_iso" in time_data
    assert "current_timestamp" in time_data
    
    # Verify values
    assert time_data["current_time"] == "2025-01-01T12:00:00+00:00"
    assert time_data["current_iso"] == "2025-01-01T12:00:00+00:00"
    assert time_data["current_timestamp"] == 1735732800.0  # Unix timestamp for 2025-01-01 12:00:00 UTC


def test_get_current_time_no_service(client):
    """Test GET /v1/time/current when service is unavailable."""
    # Remove time service
    client.app.state.time_service = None
    
    response = client.get("/v1/time/current")
    
    assert response.status_code == 503
    assert "Time service not available" in response.json()["detail"]


def test_get_uptime(client):
    """Test GET /v1/time/uptime endpoint."""
    response = client.get("/v1/time/uptime")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert "data" in data
    assert "metadata" in data
    
    # Check data fields
    uptime_data = data["data"]
    assert "service_name" in uptime_data
    assert "uptime_seconds" in uptime_data
    assert "start_time" in uptime_data
    assert "current_time" in uptime_data
    
    # Verify values
    assert uptime_data["service_name"] == "TimeService"
    assert uptime_data["uptime_seconds"] == 43200.0  # 12 hours difference
    assert uptime_data["start_time"] == "2025-01-01T00:00:00+00:00"
    assert uptime_data["current_time"] == "2025-01-01T12:00:00+00:00"


def test_get_uptime_no_start_time(client):
    """Test GET /v1/time/uptime when service has no start time."""
    # Remove start time
    client.app.state.time_service._start_time = None
    
    response = client.get("/v1/time/uptime")
    
    assert response.status_code == 200
    data = response.json()
    
    uptime_data = data["data"]
    assert uptime_data["uptime_seconds"] == 0.0
    assert uptime_data["start_time"] == uptime_data["current_time"]


def test_get_time_sync_status(client):
    """Test GET /v1/time/sync endpoint."""
    response = client.get("/v1/time/sync")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert "data" in data
    assert "metadata" in data
    
    # Check data fields
    sync_data = data["data"]
    assert "is_synchronized" in sync_data
    assert "sync_source" in sync_data
    assert "last_sync" in sync_data
    assert "drift_ms" in sync_data
    assert "is_mocked" in sync_data
    
    # Verify values
    assert sync_data["is_synchronized"] is True
    assert sync_data["sync_source"] == "system"
    assert sync_data["last_sync"] == "2025-01-01T00:00:00+00:00"
    assert sync_data["drift_ms"] == 0.0
    assert sync_data["is_mocked"] is False


def test_get_time_sync_status_mocked(client):
    """Test GET /v1/time/sync when time is mocked."""
    # Set mock time
    mock_time = datetime(2025, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
    client.app.state.time_service._mock_time = mock_time
    
    response = client.get("/v1/time/sync")
    
    assert response.status_code == 200
    data = response.json()
    
    sync_data = data["data"]
    assert sync_data["is_synchronized"] is False
    assert sync_data["sync_source"] == "mock"
    assert sync_data["is_mocked"] is True


def test_time_service_error_handling(client):
    """Test error handling when time service raises exception."""
    # Mock time service to raise exception
    mock_service = Mock(spec=TimeServiceProtocol)
    mock_service.now.side_effect = Exception("Time service error")
    mock_service.now_iso.side_effect = Exception("Time service error")
    mock_service.timestamp.side_effect = Exception("Time service error")
    
    client.app.state.time_service = mock_service
    
    # Test current time endpoint
    response = client.get("/v1/time/current")
    assert response.status_code == 500
    assert "Failed to get current time" in response.json()["detail"]
    
    # Test uptime endpoint
    response = client.get("/v1/time/uptime")
    assert response.status_code == 500
    assert "Failed to get uptime" in response.json()["detail"]
    
    # Test sync endpoint
    response = client.get("/v1/time/sync")
    assert response.status_code == 500
    assert "Failed to get sync status" in response.json()["detail"]


def test_metadata_in_responses(client):
    """Test that all responses include proper metadata."""
    endpoints = [
        "/v1/time/current",
        "/v1/time/uptime",
        "/v1/time/sync"
    ]
    
    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200
        
        data = response.json()
        assert "metadata" in data
        
        metadata = data["metadata"]
        assert "timestamp" in metadata
        assert "request_id" in metadata
        assert "duration_ms" in metadata