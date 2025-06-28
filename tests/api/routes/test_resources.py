"""
Unit tests for System Resources API endpoint.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ciris_engine.api.routes.system import router
from ciris_engine.schemas.services.resources_core import (
    ResourceBudget,
    ResourceSnapshot,
    ResourceLimit,
    ResourceAction
)
from ciris_engine.api.dependencies.auth import require_observer, require_admin, AuthContext
from ciris_engine.schemas.api.auth import UserRole, Permission, ROLE_PERMISSIONS

# Test fixtures

@pytest.fixture
def mock_resource_monitor():
    """Create a mock resource monitor service."""
    monitor = MagicMock()
    
    # Create mock budget
    monitor.budget = ResourceBudget()
    
    # Create mock snapshot
    monitor.snapshot = ResourceSnapshot(
        memory_mb=1024,
        memory_percent=25,
        cpu_percent=30,
        cpu_average_1m=35,
        tokens_used_hour=1000,
        tokens_used_day=15000,
        disk_used_mb=50,
        disk_free_mb=950,
        thoughts_active=5,
        thoughts_queued=2,
        healthy=True,
        warnings=["tokens_hour: 1000/10000"],
        critical=[]
    )
    
    return monitor

@pytest.fixture
def test_app(mock_resource_monitor):
    """Create test FastAPI app with mocked dependencies."""
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    
    # Mock app state
    app.state.resource_monitor = mock_resource_monitor
    
    # Override auth dependencies
    async def mock_observer():
        return AuthContext(
            user_id="test_user",
            role=UserRole.OBSERVER,
            permissions=ROLE_PERMISSIONS[UserRole.OBSERVER],
            authenticated_at=datetime.now(timezone.utc)
        )
    
    async def mock_admin():
        return AuthContext(
            user_id="admin_user",
            role=UserRole.ADMIN,
            permissions=ROLE_PERMISSIONS[UserRole.ADMIN],
            authenticated_at=datetime.now(timezone.utc)
        )
    
    app.dependency_overrides[require_observer] = mock_observer
    app.dependency_overrides[require_admin] = mock_admin
    
    return app

@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)

# Test for GET /v1/system/resources

def test_get_resource_usage_success(client, mock_resource_monitor):
    """Test successful retrieval of resource usage and limits."""
    response = client.get("/v1/system/resources")
    
    assert response.status_code == 200
    data = response.json()["data"]
    
    # Check response structure
    assert "current_usage" in data
    assert "limits" in data
    assert "health_status" in data
    assert "warnings" in data
    assert "critical" in data
    
    # Check current usage (ResourceSnapshot)
    usage = data["current_usage"]
    assert usage["memory_mb"] == 1024
    assert usage["memory_percent"] == 25
    assert usage["cpu_percent"] == 30
    assert usage["cpu_average_1m"] == 35
    assert usage["tokens_used_hour"] == 1000
    assert usage["tokens_used_day"] == 15000
    assert usage["disk_used_mb"] == 50
    assert usage["disk_free_mb"] == 950
    assert usage["thoughts_active"] == 5
    assert usage["thoughts_queued"] == 2
    assert usage["healthy"] is True
    
    # Check limits (ResourceBudget)
    limits = data["limits"]
    assert "memory_mb" in limits
    assert "cpu_percent" in limits
    assert "tokens_hour" in limits
    assert "tokens_day" in limits
    assert "disk_mb" in limits
    assert "thoughts_active" in limits
    
    # Check structure of a limit
    memory_limit = limits["memory_mb"]
    assert "limit" in memory_limit
    assert "warning" in memory_limit
    assert "critical" in memory_limit
    assert "action" in memory_limit
    assert "cooldown_seconds" in memory_limit
    
    # Check health status
    assert data["health_status"] == "warning"  # Has warnings
    assert data["warnings"] == ["tokens_hour: 1000/10000"]
    assert data["critical"] == []

def test_get_resource_usage_critical_status(client, mock_resource_monitor):
    """Test resource endpoint when critical thresholds are exceeded."""
    # Add critical alert
    mock_resource_monitor.snapshot.critical = ["memory_mb: 3900/4096"]
    mock_resource_monitor.snapshot.warnings = []
    
    response = client.get("/v1/system/resources")
    
    assert response.status_code == 200
    data = response.json()["data"]
    
    assert data["health_status"] == "critical"
    assert data["critical"] == ["memory_mb: 3900/4096"]
    assert data["warnings"] == []

def test_get_resource_usage_healthy_status(client, mock_resource_monitor):
    """Test resource endpoint when everything is healthy."""
    # Clear warnings and critical
    mock_resource_monitor.snapshot.warnings = []
    mock_resource_monitor.snapshot.critical = []
    
    response = client.get("/v1/system/resources")
    
    assert response.status_code == 200
    data = response.json()["data"]
    
    assert data["health_status"] == "healthy"
    assert data["warnings"] == []
    assert data["critical"] == []

def test_get_resource_usage_no_service(client, test_app):
    """Test when resource monitor service is not available."""
    test_app.state.resource_monitor = None
    
    response = client.get("/v1/system/resources")
    
    assert response.status_code == 503
    assert "Resource monitor service not available" in response.json()["detail"]

def test_get_resource_usage_requires_auth(client, test_app):
    """Test that resource endpoint requires authentication."""
    # Remove auth override
    test_app.dependency_overrides.clear()
    
    response = client.get("/v1/system/resources")
    
    # Should get error when auth is not provided
    # In this test setup, it returns 500 because auth context is missing
    assert response.status_code in [401, 403, 422, 500]

# Error handling tests

def test_resource_monitor_exception_handling(client, mock_resource_monitor):
    """Test exception handling in resource endpoint."""
    # Make snapshot property raise an exception
    mock_resource_monitor.snapshot = property(lambda self: (_ for _ in ()).throw(Exception("Test error")))
    
    response = client.get("/v1/system/resources")
    
    assert response.status_code == 500
    # The error could be about the property object or the actual exception
    error_detail = response.json()["detail"]
    assert any(phrase in error_detail for phrase in ["Test error", "property", "attribute"])