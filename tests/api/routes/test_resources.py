"""
Unit tests for Resource Monitor Service API endpoints.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ciris_engine.api.routes.resources import router
from ciris_engine.schemas.services.resources_core import (
    ResourceBudget,
    ResourceSnapshot,
    ResourceLimit,
    ResourceAction,
    ResourceAlert
)
from ciris_engine.api.dependencies.auth import require_observer, require_admin, AuthContext

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
            role="OBSERVER",
            permissions=["read"]
        )
    
    async def mock_admin():
        return AuthContext(
            user_id="admin_user",
            role="ADMIN",
            permissions=["read", "write", "admin"]
        )
    
    app.dependency_overrides[require_observer] = mock_observer
    app.dependency_overrides[require_admin] = mock_admin
    
    return app

@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)

# Tests for GET /v1/resources/limits

def test_get_resource_limits_success(client, mock_resource_monitor):
    """Test successful retrieval of resource limits."""
    response = client.get("/v1/resources/limits")
    
    assert response.status_code == 200
    data = response.json()["data"]
    
    assert "memory_mb" in data
    assert "cpu_percent" in data
    assert "tokens_hour" in data
    assert "tokens_day" in data
    assert "disk_mb" in data
    assert "thoughts_active" in data
    assert "effective_from" in data
    
    # Check structure of a limit
    memory_limit = data["memory_mb"]
    assert "limit" in memory_limit
    assert "warning" in memory_limit
    assert "critical" in memory_limit
    assert "action" in memory_limit
    assert "cooldown_seconds" in memory_limit

def test_get_resource_limits_no_service(client, test_app):
    """Test when resource monitor service is not available."""
    test_app.state.resource_monitor = None
    
    response = client.get("/v1/resources/limits")
    
    assert response.status_code == 503
    assert "Resource monitor service not available" in response.json()["detail"]

# Tests for GET /v1/resources/usage

def test_get_resource_usage_success(client, mock_resource_monitor):
    """Test successful retrieval of resource usage."""
    response = client.get("/v1/resources/usage")
    
    assert response.status_code == 200
    data = response.json()["data"]
    
    assert "snapshot" in data
    assert "budget" in data
    assert "timestamp" in data
    
    # Check snapshot data
    snapshot = data["snapshot"]
    assert snapshot["memory_mb"] == 1024
    assert snapshot["cpu_percent"] == 30
    assert snapshot["tokens_used_hour"] == 1000
    assert snapshot["healthy"] is True
    assert len(snapshot["warnings"]) == 1

def test_get_resource_usage_no_service(client, test_app):
    """Test when resource monitor service is not available."""
    test_app.state.resource_monitor = None
    
    response = client.get("/v1/resources/usage")
    
    assert response.status_code == 503

# Tests for GET /v1/resources/alerts

def test_get_resource_alerts_success(client, mock_resource_monitor):
    """Test successful retrieval of resource alerts."""
    response = client.get("/v1/resources/alerts")
    
    assert response.status_code == 200
    data = response.json()["data"]
    
    assert isinstance(data, list)
    # Should have at least one alert from the warning in snapshot
    assert len(data) >= 1
    
    # Check alert structure
    if data:
        alert = data[0]
        assert "resource_type" in alert
        assert "current_value" in alert
        assert "limit_value" in alert
        assert "severity" in alert
        assert "action_taken" in alert
        assert "timestamp" in alert
        assert "message" in alert

def test_get_resource_alerts_with_critical(client, mock_resource_monitor):
    """Test alerts when critical thresholds are exceeded."""
    # Add critical alert
    mock_resource_monitor.snapshot.critical = ["memory_mb: 3900/4096"]
    mock_resource_monitor.snapshot.memory_mb = 3900
    
    response = client.get("/v1/resources/alerts")
    
    assert response.status_code == 200
    data = response.json()["data"]
    
    # Should have critical alerts
    critical_alerts = [a for a in data if a["severity"] == "critical"]
    assert len(critical_alerts) > 0

def test_get_resource_alerts_with_hours_param(client):
    """Test alerts with hours parameter."""
    response = client.get("/v1/resources/alerts?hours=48")
    
    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)

# Tests for GET /v1/resources/predictions

def test_get_resource_predictions_success(client, mock_resource_monitor):
    """Test successful retrieval of resource predictions."""
    response = client.get("/v1/resources/predictions")
    
    assert response.status_code == 200
    data = response.json()["data"]
    
    assert "predictions" in data
    assert "analysis_window_hours" in data
    assert "generated_at" in data
    
    predictions = data["predictions"]
    assert len(predictions) > 0
    
    # Check prediction structure
    for pred in predictions:
        assert "resource_name" in pred
        assert "current_usage" in pred
        assert "predicted_usage_1h" in pred
        assert "predicted_usage_24h" in pred
        assert "time_to_limit" in pred  # Can be null
        assert "confidence" in pred
        assert "trend" in pred
        assert pred["confidence"] >= 0 and pred["confidence"] <= 1

def test_get_resource_predictions_includes_all_resources(client, mock_resource_monitor):
    """Test that predictions include all monitored resources."""
    response = client.get("/v1/resources/predictions")
    
    assert response.status_code == 200
    data = response.json()["data"]
    
    predictions = data["predictions"]
    resource_names = [p["resource_name"] for p in predictions]
    
    expected_resources = ["memory_mb", "cpu_percent", "tokens_hour", "tokens_day", "thoughts_active"]
    for resource in expected_resources:
        assert resource in resource_names

# Tests for POST /v1/resources/alerts/config

def test_configure_alerts_success(client, mock_resource_monitor):
    """Test successful alert configuration update."""
    config_data = {
        "resource_name": "memory_mb",
        "warning_threshold": 2500,
        "critical_threshold": 3500,
        "action": "THROTTLE",
        "cooldown_seconds": 120
    }
    
    response = client.post("/v1/resources/alerts/config", json=config_data)
    
    assert response.status_code == 200
    data = response.json()["data"]
    
    assert data["updated"] is True
    assert data["resource_name"] == "memory_mb"
    assert "new_config" in data
    assert "previous_config" in data
    
    # Check that values were updated
    new_config = data["new_config"]
    assert new_config["warning"] == 2500
    assert new_config["critical"] == 3500
    assert new_config["action"] == "THROTTLE"
    assert new_config["cooldown_seconds"] == 120

def test_configure_alerts_invalid_resource(client):
    """Test configuration with invalid resource name."""
    config_data = {
        "resource_name": "invalid_resource",
        "warning_threshold": 100
    }
    
    response = client.post("/v1/resources/alerts/config", json=config_data)
    
    assert response.status_code == 400
    assert "Invalid resource name" in response.json()["detail"]

def test_configure_alerts_invalid_thresholds(client):
    """Test configuration with invalid threshold values."""
    # Warning threshold too high
    config_data = {
        "resource_name": "memory_mb",
        "warning_threshold": 5000  # Higher than limit (4096)
    }
    
    response = client.post("/v1/resources/alerts/config", json=config_data)
    
    assert response.status_code == 400
    assert "Warning threshold must be less than limit" in response.json()["detail"]

def test_configure_alerts_critical_less_than_warning(client, mock_resource_monitor):
    """Test configuration where critical is less than warning."""
    # Set current warning to 3000
    mock_resource_monitor.budget.memory_mb.warning = 3000
    
    config_data = {
        "resource_name": "memory_mb",
        "critical_threshold": 2000  # Less than warning
    }
    
    response = client.post("/v1/resources/alerts/config", json=config_data)
    
    assert response.status_code == 400
    assert "Critical threshold must be greater than warning threshold" in response.json()["detail"]

def test_configure_alerts_partial_update(client):
    """Test partial configuration update."""
    config_data = {
        "resource_name": "cpu_percent",
        "action": "REJECT"  # Only update action
    }
    
    response = client.post("/v1/resources/alerts/config", json=config_data)
    
    assert response.status_code == 200
    data = response.json()["data"]
    
    assert data["updated"] is True
    assert data["new_config"]["action"] == "REJECT"
    # Other values should remain unchanged
    assert data["new_config"]["warning"] == data["previous_config"]["warning"]

def test_configure_alerts_no_changes(client):
    """Test configuration request with no actual changes."""
    config_data = {
        "resource_name": "disk_mb"
        # No actual changes specified
    }
    
    response = client.post("/v1/resources/alerts/config", json=config_data)
    
    assert response.status_code == 200
    data = response.json()["data"]
    
    assert data["updated"] is False
    assert data["new_config"] == data["previous_config"]

# Error handling tests

def test_resource_monitor_exception_handling(client, mock_resource_monitor):
    """Test exception handling in resource endpoints."""
    # Make budget property raise an exception
    mock_resource_monitor.budget = property(lambda self: (_ for _ in ()).throw(Exception("Test error")))
    
    response = client.get("/v1/resources/limits")
    
    assert response.status_code == 500
    assert "Test error" in response.json()["detail"]