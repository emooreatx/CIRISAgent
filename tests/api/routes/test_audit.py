"""
Tests for audit API routes.
"""
import pytest
from datetime import datetime, timezone, timedelta
from typing import List
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

from ciris_engine.schemas.services.nodes import AuditEntry, AuditEntryContext
from ciris_engine.schemas.services.graph.audit import AuditQuery, VerificationReport
from ciris_engine.protocols.services.graph.audit import AuditServiceProtocol

# Test fixtures

@pytest.fixture
def mock_audit_service():
    """Create mock audit service."""
    from ciris_engine.schemas.services.graph_core import GraphScope
    
    service = AsyncMock(spec=AuditServiceProtocol)
    
    # Create sample audit entries
    now = datetime.now(timezone.utc)
    sample_entries = [
        AuditEntry(
            id="audit_001",
            scope=GraphScope.LOCAL,
            attributes={},
            action="user_login",
            actor="user123",
            timestamp=now - timedelta(hours=1),
            context=AuditEntryContext(
                service_name="auth_service",
                method_name="login",
                user_id="user123"
            ),
            signature="sig1",
            hash_chain="hash0",
            created_at=now - timedelta(hours=1),
            updated_at=now - timedelta(hours=1),
            created_by="audit_service",
            updated_by="audit_service"
        ),
        AuditEntry(
            id="audit_002",
            scope=GraphScope.LOCAL,
            attributes={},
            action="config_update",
            actor="admin456",
            timestamp=now - timedelta(minutes=30),
            context=AuditEntryContext(
                service_name="config_service",
                method_name="update_config",
                user_id="admin456",
                additional_data={"key": "some_config", "old_value": "old", "new_value": "new"}
            ),
            signature="sig2",
            hash_chain="hash1",
            created_at=now - timedelta(minutes=30),
            updated_at=now - timedelta(minutes=30),
            created_by="audit_service",
            updated_by="audit_service"
        ),
        AuditEntry(
            id="audit_003",
            scope=GraphScope.LOCAL,
            attributes={},
            action="task_complete",
            actor="agent",
            timestamp=now - timedelta(minutes=15),
            context=AuditEntryContext(
                service_name="task_scheduler",
                method_name="complete_task",
                correlation_id="task789"
            ),
            signature="sig3",
            hash_chain="hash2",
            created_at=now - timedelta(minutes=15),
            updated_at=now - timedelta(minutes=15),
            created_by="audit_service",
            updated_by="audit_service"
        )
    ]
    
    # Set up mock responses
    service.query_audit_trail.return_value = sample_entries
    service.get_verification_report.return_value = VerificationReport(
        verified=True,
        total_entries=1000,
        valid_entries=998,
        invalid_entries=2,
        chain_intact=True,
        verification_started=now - timedelta(seconds=5),
        verification_completed=now,
        duration_ms=5000.0
    )
    service.export_audit_data.return_value = '{"action":"user_login","actor":"user123"}\n{"action":"config_update","actor":"admin456"}'
    
    return service

@pytest.fixture
def app_with_audit(mock_audit_service, mock_auth_service):
    """Create FastAPI app with audit routes."""
    from fastapi import FastAPI
    from ciris_engine.api.routes.audit import router
    
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    
    # Add services to app state
    app.state.audit_service = mock_audit_service
    app.state.auth_service = mock_auth_service
    
    return app

# Tests

class TestAuditEndpoints:
    """Test audit API endpoints."""
    
    def test_get_audit_entries_observer(self, app_with_audit, observer_headers):
        """Test getting audit entries as observer."""
        client = TestClient(app_with_audit)
        
        response = client.get(
            "/v1/audit/entries",
            headers=observer_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "entries" in data["data"]
        assert len(data["data"]["entries"]) == 3
        
        # Check first entry structure
        first_entry = data["data"]["entries"][0]
        assert first_entry["action"] == "user_login"
        assert first_entry["actor"] == "user123"
        assert "timestamp" in first_entry
        assert "context" in first_entry
        assert first_entry["signature"] == "sig1"
    
    def test_get_audit_entries_with_filters(self, app_with_audit, observer_headers, mock_audit_service):
        """Test getting audit entries with filters."""
        client = TestClient(app_with_audit)
        
        # Filter by actor
        from ciris_engine.schemas.services.graph_core import GraphScope
        mock_audit_service.query_audit_trail.return_value = [
            AuditEntry(
                id="audit_filtered",
                scope=GraphScope.LOCAL,
                attributes={},
                action="user_login",
                actor="user123",
                timestamp=datetime.now(timezone.utc),
                context=AuditEntryContext(),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                created_by="audit_service",
                updated_by="audit_service"
            )
        ]
        
        response = client.get(
            "/v1/audit/entries?actor=user123&limit=10",
            headers=observer_headers
        )
        
        assert response.status_code == 200
        
        # Verify query was called with correct parameters
        mock_audit_service.query_audit_trail.assert_called()
        call_args = mock_audit_service.query_audit_trail.call_args[0][0]
        assert isinstance(call_args, AuditQuery)
        assert call_args.actor == "user123"
        assert call_args.limit == 10
    
    def test_get_audit_entries_unauthorized(self, app_with_audit):
        """Test getting audit entries without auth."""
        client = TestClient(app_with_audit)
        
        response = client.get("/v1/audit/entries")
        assert response.status_code == 401
    
    def test_get_specific_audit_entry(self, app_with_audit, observer_headers):
        """Test getting specific audit entry."""
        client = TestClient(app_with_audit)
        
        response = client.get(
            "/v1/audit/entries/audit_001",  # Use an ID that exists in our mock data
            headers=observer_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "entry" in data["data"]
        assert data["data"]["entry"]["action"] == "user_login"
    
    def test_get_audit_entry_not_found(self, app_with_audit, observer_headers, mock_audit_service):
        """Test getting non-existent audit entry."""
        client = TestClient(app_with_audit)
        
        # Mock empty result
        mock_audit_service.query_audit_trail.return_value = []
        
        response = client.get(
            "/v1/audit/entries/nonexistent",
            headers=observer_headers
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    def test_search_audit_trails(self, app_with_audit, observer_headers):
        """Test searching audit trails."""
        client = TestClient(app_with_audit)
        
        response = client.get(
            "/v1/audit/search?search_text=login&severity=info",
            headers=observer_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "entries" in data["data"]
    
    def test_verify_audit_entry_admin_only(self, app_with_audit, observer_headers, admin_headers):
        """Test audit verification requires admin role."""
        client = TestClient(app_with_audit)
        
        # Observer should be forbidden
        response = client.get(
            "/v1/audit/verify/audit_123",
            headers=observer_headers
        )
        assert response.status_code == 403
        
        # Admin should succeed
        response = client.get(
            "/v1/audit/verify/audit_123",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["verified"] == True
        assert data["data"]["total_entries"] == 1000
        assert data["data"]["valid_entries"] == 998
    
    def test_export_audit_data_admin_only(self, app_with_audit, observer_headers, admin_headers):
        """Test audit export requires admin role."""
        client = TestClient(app_with_audit)
        
        # Observer should be forbidden
        response = client.get(
            "/v1/audit/export",
            headers=observer_headers
        )
        assert response.status_code == 403
        
        # Admin should succeed
        response = client.get(
            "/v1/audit/export?format=jsonl",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["format"] == "jsonl"
        assert data["data"]["total_entries"] == 2
        assert data["data"]["export_data"] is not None  # Small export, inline data
    
    def test_export_audit_data_with_date_range(self, app_with_audit, admin_headers, mock_audit_service):
        """Test audit export with date range."""
        client = TestClient(app_with_audit)
        
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)
        
        from urllib.parse import quote
        response = client.get(
            f"/v1/audit/export?start_date={quote(start_date.isoformat())}&end_date={quote(end_date.isoformat())}&format=csv",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        
        # Verify export was called with correct parameters
        mock_audit_service.export_audit_data.assert_called_with(
            start_date=pytest.approx(start_date, abs=timedelta(seconds=1)),
            end_date=pytest.approx(end_date, abs=timedelta(seconds=1)),
            format="csv"
        )
    
    def test_export_invalid_format(self, app_with_audit, admin_headers):
        """Test export with invalid format."""
        client = TestClient(app_with_audit)
        
        response = client.get(
            "/v1/audit/export?format=invalid",
            headers=admin_headers
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_pagination(self, app_with_audit, observer_headers):
        """Test pagination parameters."""
        client = TestClient(app_with_audit)
        
        response = client.get(
            "/v1/audit/entries?limit=50&offset=100",
            headers=observer_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["limit"] == 50
        assert data["data"]["offset"] == 100
    
    def test_service_unavailable(self, observer_headers, mock_auth_service):
        """Test when audit service is not available."""
        from fastapi import FastAPI
        from ciris_engine.api.routes.audit import router
        
        app = FastAPI()
        app.include_router(router, prefix="/v1")
        # Add auth service but not audit service
        app.state.auth_service = mock_auth_service
        
        client = TestClient(app)
        
        response = client.get(
            "/v1/audit/entries",
            headers=observer_headers
        )
        
        assert response.status_code == 503
        assert "not available" in response.json()["detail"]
    
    def test_time_range_query(self, app_with_audit, observer_headers, mock_audit_service):
        """Test querying with time range."""
        client = TestClient(app_with_audit)
        
        start_time = datetime.now(timezone.utc) - timedelta(hours=2)
        end_time = datetime.now(timezone.utc)
        
        from urllib.parse import quote
        response = client.get(
            f"/v1/audit/entries?start_time={quote(start_time.isoformat())}&end_time={quote(end_time.isoformat())}",
            headers=observer_headers
        )
        
        assert response.status_code == 200
        
        # Verify query parameters
        call_args = mock_audit_service.query_audit_trail.call_args[0][0]
        assert call_args.start_time is not None
        assert call_args.end_time is not None
    
    def test_complex_search(self, app_with_audit, observer_headers, mock_audit_service):
        """Test complex search with multiple filters."""
        client = TestClient(app_with_audit)
        
        response = client.get(
            "/v1/audit/search?search_text=config&entity_id=system&severity=warning&outcome=success",
            headers=observer_headers
        )
        
        assert response.status_code == 200
        
        # Verify all filters were passed
        call_args = mock_audit_service.query_audit_trail.call_args[0][0]
        assert call_args.search_text == "config"
        assert call_args.entity_id == "system"
        assert call_args.severity == "warning"
        assert call_args.outcome == "success"