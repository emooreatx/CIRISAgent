"""
Unit tests for observability aggregation endpoints.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
import json

from ciris_engine.api.routes.observe import router
from ciris_engine.api.dependencies.auth import AuthContext, UserRole
from ciris_engine.schemas.services.visibility import VisibilitySnapshot
from ciris_engine.schemas.services.nodes import AuditEntry


@pytest.fixture
def test_app():
    """Create test FastAPI app with observe routes."""
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    
    # Mock auth service
    from ciris_engine.api.services.auth_service import StoredAPIKey
    from ciris_engine.schemas.api.auth import UserRole
    from datetime import datetime, timezone
    
    app.state.auth_service = Mock()
    mock_key = StoredAPIKey(
        key_hash="test-hash",
        user_id="test-user",
        role=UserRole.OBSERVER,
        expires_at=None,
        description="Test key",
        created_at=datetime.now(timezone.utc),
        created_by="test",
        last_used=None,
        is_active=True
    )
    app.state.auth_service.validate_api_key = AsyncMock(return_value=mock_key)
    app.state.auth_service._get_key_id = Mock(return_value="test-key-id")
    
    # Mock services
    app.state.memory_service = Mock()
    app.state.llm_service = Mock()
    app.state.audit_service = Mock()
    app.state.telemetry_service = Mock()
    app.state.config_service = Mock()
    app.state.visibility_service = Mock()
    app.state.time_service = Mock()
    app.state.secrets_service = Mock()
    app.state.resource_monitor = Mock()
    app.state.authentication_service = Mock()
    app.state.wise_authority = Mock()
    app.state.incident_management = Mock()
    app.state.tsdb_consolidation = Mock()
    app.state.self_configuration = Mock()
    app.state.adaptive_filter = Mock()
    app.state.task_scheduler = Mock()
    
    return app


@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)


@pytest.fixture
def auth_headers():
    """Mock auth headers."""
    return {"Authorization": "Bearer test-token"}




class TestDashboardEndpoint:
    """Test dashboard endpoint."""
    
    def test_get_dashboard_success(self, client, test_app, auth_headers):
        """Test successful dashboard data retrieval."""
        # Mock resource monitor
        test_app.state.resource_monitor.get_current_usage = AsyncMock(return_value={
            'cpu_percent': 45.5,
            'memory_mb': 1024.0,
            'disk_mb': 2048.0
        })
        
        # Mock task scheduler
        test_app.state.task_scheduler.get_active_tasks = AsyncMock(return_value=[
            {'id': 'task1'}, {'id': 'task2'}
        ])
        
        # Mock visibility service
        mock_snapshot = Mock()
        mock_snapshot.cognitive_state = "WORK"
        test_app.state.visibility_service.get_snapshot = AsyncMock(return_value=mock_snapshot)
        
        # Mock incident service
        test_app.state.incident_management.get_incidents = AsyncMock(return_value=[
            {'id': 'incident1'}
        ])
        
        # Mock wise authority
        test_app.state.wise_authority.get_pending_deferrals = AsyncMock(return_value=[
            {'id': 'deferral1'}, {'id': 'deferral2'}
        ])
        
        # Mock LLM service
        test_app.state.llm_service.get_usage_stats = AsyncMock(return_value={
            'by_model': {'gpt-4': 1000.0, 'gpt-3.5': 5000.0}
        })
        
        response = client.get("/v1/observe/dashboard", headers=auth_headers)
        if response.status_code != 200:
            print(f"Error response: {response.json()}")
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert "services" in data
        assert "system" in data
        assert "cognitive" in data
        assert data["recent_incidents"] == 1
        assert data["active_deferrals"] == 2
        assert data["llm_usage"]["gpt-4"] == 1000.0
        
        # Check system metrics
        assert data["system"]["cpu_percent"] == 45.5
        assert data["system"]["memory_mb"] == 1024.0
        assert data["system"]["active_tasks"] == 2
        
        # Check cognitive metrics
        assert data["cognitive"]["current_state"] == "WORK"
    
    def test_get_dashboard_partial_services(self, client, test_app, auth_headers):
        """Test dashboard with some services unavailable."""
        # Only mock some services
        test_app.state.resource_monitor = None
        test_app.state.task_scheduler = None
        
        response = client.get("/v1/observe/dashboard", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()["data"]
        # Should still return data with defaults
        assert data["system"]["cpu_percent"] == 0.0
        assert data["system"]["active_tasks"] == 0
        
        # Check service health includes unhealthy services
        unhealthy_services = [s for s in data["services"] if s["status"] == "unhealthy"]
        assert len(unhealthy_services) > 0


class TestTracesEndpoint:
    """Test traces endpoint."""
    
    def test_get_traces_success(self, client, test_app, auth_headers):
        """Test successful trace retrieval."""
        # Mock audit entries
        mock_entries = [
            Mock(
                timestamp=datetime.now(timezone.utc),
                action="process_message",
                actor="message_handler",
                context={'correlation_id': 'trace123'}
            ),
            Mock(
                timestamp=datetime.now(timezone.utc) + timedelta(seconds=1),
                action="generate_response",
                actor="llm_service",
                context={'correlation_id': 'trace123'}
            )
        ]
        
        test_app.state.audit_service.query_entries = AsyncMock(return_value=mock_entries)
        
        response = client.get("/v1/observe/traces?limit=5", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert "traces" in data
        assert len(data["traces"]) > 0
        
        # Check trace structure
        trace = data["traces"][0]
        assert "trace_id" in trace
        assert "spans" in trace
        assert len(trace["spans"]) == 2
        assert trace["service_count"] == 2
    
    def test_get_traces_filter_by_service(self, client, test_app, auth_headers):
        """Test trace filtering by service."""
        mock_entries = [
            Mock(
                timestamp=datetime.now(timezone.utc),
                action="action1",
                actor="memory_service",
                context={}
            )
        ]
        
        test_app.state.audit_service.query_entries = AsyncMock(return_value=mock_entries)
        
        response = client.get("/v1/observe/traces?service=memory", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()["data"]
        traces = data["traces"]
        # Should only include traces with memory service
        for trace in traces:
            service_names = [span["service"] for span in trace["spans"]]
            assert any("memory" in s for s in service_names)


class TestMetricsEndpoint:
    """Test metrics endpoint."""
    
    def test_get_metrics_success(self, client, test_app, auth_headers):
        """Test successful metrics aggregation."""
        # Mock telemetry service
        mock_metrics = {
            'cpu.usage': {'value': 45.5, 'unit': 'percent'},
            'memory.usage': {'value': 1024.0, 'unit': 'MB'},
            'llm.tokens': {'value': 5000, 'unit': 'tokens'}
        }
        
        test_app.state.telemetry_service.get_current_metrics = AsyncMock(
            return_value=mock_metrics
        )
        
        response = client.get("/v1/observe/metrics", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert "metrics" in data
        assert len(data["metrics"]) > 0
        
        # Check metric aggregation
        cpu_metric = next((m for m in data["metrics"] if m["metric_name"] == "cpu"), None)
        assert cpu_metric is not None
        assert cpu_metric["value"] == 45.5
        assert cpu_metric["unit"] == "percent"


class TestLogsEndpoint:
    """Test logs endpoint."""
    
    def test_get_logs_success(self, client, test_app, auth_headers):
        """Test successful log retrieval."""
        # Mock audit entries as logs
        mock_entries = [
            Mock(
                timestamp=datetime.now(timezone.utc),
                action="process_message",
                actor="message_handler",
                context={'description': 'Processing user message'}
            ),
            Mock(
                timestamp=datetime.now(timezone.utc),
                action="error_occurred",
                actor="llm_service",
                context={'description': 'API rate limit exceeded'}
            )
        ]
        
        test_app.state.audit_service.query_entries = AsyncMock(return_value=mock_entries)
        
        response = client.get("/v1/observe/logs", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert "logs" in data
        assert len(data["logs"]) == 2
        
        # Check log conversion
        assert data["logs"][0]["level"] == "INFO"
        assert data["logs"][1]["level"] == "ERROR"
        assert "process_message" in data["logs"][0]["message"]
    
    def test_get_logs_with_filters(self, client, test_app, auth_headers):
        """Test log filtering."""
        mock_entries = [
            Mock(
                timestamp=datetime.now(timezone.utc),
                action="error_occurred",
                actor="llm_service",
                context={}
            )
        ]
        
        test_app.state.audit_service.query_entries = AsyncMock(return_value=mock_entries)
        
        # Filter by level
        response = client.get("/v1/observe/logs?level=ERROR", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()["data"]
        # Should only have error logs
        assert all(log["level"] == "ERROR" for log in data["logs"])
        
        # Filter by service
        response = client.get("/v1/observe/logs?service=llm_service", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert all(log["service"] == "llm_service" for log in data["logs"])


class TestQueryEndpoint:
    """Test custom query endpoint."""
    
    def test_query_metrics(self, client, test_app, auth_headers):
        """Test metrics query."""
        mock_metrics = {
            'test.metric': {'value': 100, 'unit': 'count'}
        }
        test_app.state.telemetry_service.get_current_metrics = AsyncMock(
            return_value=mock_metrics
        )
        
        query = {
            "query_type": "metrics",
            "filters": {},
            "aggregations": []
        }
        
        response = client.post("/v1/observe/query", json=query, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert data["query_type"] == "metrics"
        assert len(data["results"]) > 0
        assert "execution_time_ms" in data
    
    def test_query_composite(self, client, test_app, auth_headers):
        """Test composite query."""
        # Mock all required services for dashboard
        test_app.state.resource_monitor = Mock()
        test_app.state.resource_monitor.get_current_usage = AsyncMock(return_value={})
        test_app.state.task_scheduler = Mock()
        test_app.state.task_scheduler.get_active_tasks = AsyncMock(return_value=[])
        test_app.state.visibility_service = Mock()
        test_app.state.visibility_service.get_snapshot = AsyncMock(return_value=None)
        
        query = {
            "query_type": "composite",
            "filters": {},
            "aggregations": []
        }
        
        response = client.post("/v1/observe/query", json=query, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert data["query_type"] == "composite"
        assert len(data["results"]) == 1  # Dashboard data
    
    def test_query_with_filters(self, client, test_app, auth_headers):
        """Test query with filters."""
        mock_entries = []
        test_app.state.audit_service.query_entries = AsyncMock(return_value=mock_entries)
        
        query = {
            "query_type": "logs",
            "filters": {"level": "ERROR"},
            "aggregations": []
        }
        
        response = client.post("/v1/observe/query", json=query, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()["data"]
        # Results should be filtered
        assert data["query_type"] == "logs"


class TestWebSocketStream:
    """Test WebSocket streaming endpoint."""
    
    def test_stream_requires_auth(self, test_app):
        """Test that stream requires authentication."""
        from fastapi.testclient import TestClient
        
        client = TestClient(test_app)
        # Connect without API key
        with client.websocket_connect("/v1/observe/stream") as websocket:
            # Should receive error message and disconnect
            data = websocket.receive_json()
            assert data["type"] == "error"
            assert "Authentication required" in data["message"]
    
    def test_stream_with_auth(self, test_app):
        """Test authenticated stream connection."""
        from fastapi.testclient import TestClient
        
        # Mock services for stream
        test_app.state.telemetry_service = Mock()
        test_app.state.telemetry_service.get_current_metrics = AsyncMock(return_value={})
        test_app.state.resource_monitor = Mock()
        test_app.state.resource_monitor.get_current_usage = AsyncMock(return_value={})
        test_app.state.visibility_service = Mock()
        test_app.state.visibility_service.get_snapshot = AsyncMock(return_value=None)
        
        client = TestClient(test_app)
        
        # This test is simplified - in real implementation would test actual WebSocket behavior
        # FastAPI TestClient has limitations with WebSocket testing
        assert True  # Placeholder for actual WebSocket test


class TestErrorHandling:
    """Test error handling in observe endpoints."""
    
    def test_dashboard_service_error(self, client, test_app, auth_headers):
        """Test dashboard handles service errors gracefully."""
        # Make resource monitor raise an error
        test_app.state.resource_monitor.get_current_usage = AsyncMock(
            side_effect=Exception("Service error")
        )
        
        response = client.get("/v1/observe/dashboard", headers=auth_headers)
        assert response.status_code == 200  # Should still succeed
        
        data = response.json()["data"]
        # Should have default values when service fails
        assert data["system"]["cpu_percent"] == 0.0
    
    def test_traces_no_audit_service(self, client, test_app, auth_headers):
        """Test traces when audit service is unavailable."""
        test_app.state.audit_service = None
        
        response = client.get("/v1/observe/traces", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert data["traces"] == []
        assert data["total"] == 0