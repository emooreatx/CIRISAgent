"""
Unit tests for TSDB consolidation API routes.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

from ciris_engine.api.routes.tsdb import router
from ciris_engine.api.dependencies.auth import get_auth_context
from ciris_engine.schemas.api.auth import AuthContext, UserRole
from ciris_engine.schemas.services.nodes import TSDBSummary
from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphScope
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus


@pytest.fixture
def mock_tsdb_service():
    """Create a mock TSDB consolidation service."""
    service = AsyncMock()
    
    # Mock memory bus
    service._memory_bus = AsyncMock()
    
    # Mock service methods
    service.get_capabilities = MagicMock(return_value=ServiceCapabilities(
        service_name="TSDBConsolidationService",
        actions=["consolidate_tsdb_nodes"],
        version="1.0.0",
        dependencies=["MemoryService", "TimeService"],
        metadata={
            "consolidation_interval_hours": 6,
            "raw_retention_hours": 24
        }
    ))
    
    service.get_status = MagicMock(return_value=ServiceStatus(
        service_name="TSDBConsolidationService",
        service_type="graph_service",
        is_healthy=True,
        uptime_seconds=3600.0,
        metrics={
            "last_consolidation_timestamp": datetime.now(timezone.utc).timestamp()
        }
    ))
    
    return service


@pytest.fixture
def mock_auth_observer():
    """Mock auth dependency for observer role."""
    from ciris_engine.schemas.api.auth import Permission, ROLE_PERMISSIONS
    
    return AuthContext(
        user_id="test_observer",
        api_key_id="key_123",
        role=UserRole.OBSERVER,
        permissions=ROLE_PERMISSIONS[UserRole.OBSERVER],
        authenticated_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def mock_auth_admin():
    """Mock auth dependency for admin role."""
    from ciris_engine.schemas.api.auth import Permission, ROLE_PERMISSIONS
    
    return AuthContext(
        user_id="test_admin",
        api_key_id="key_456",
        role=UserRole.ADMIN,
        permissions=ROLE_PERMISSIONS[UserRole.ADMIN],
        authenticated_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def test_app(mock_tsdb_service):
    """Create test FastAPI app with mocked dependencies."""
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    
    # Set up app state
    app.state.tsdb_consolidation_service = mock_tsdb_service
    
    return app


@pytest.fixture
def test_client(test_app, mock_auth_observer):
    """Create test client with observer auth."""
    app = test_app
    
    # Override auth dependency
    async def mock_get_auth():
        return mock_auth_observer
    
    app.dependency_overrides[get_auth_context] = mock_get_auth
    
    return TestClient(app)


@pytest.fixture
def test_client_admin(test_app, mock_auth_admin):
    """Create test client with admin auth."""
    app = test_app
    
    # Override auth dependency
    async def mock_get_auth():
        return mock_auth_admin
    
    app.dependency_overrides[get_auth_context] = mock_get_auth
    
    return TestClient(app)


def create_mock_tsdb_summary(period_start: datetime) -> TSDBSummary:
    """Create a mock TSDBSummary for testing."""
    period_end = period_start + timedelta(hours=6)
    
    # Create the TSDBSummary with all required fields
    summary = TSDBSummary(
        period_start=period_start,
        period_end=period_end,
        period_label=f"{period_start.strftime('%Y-%m-%d')}-test",
        metrics={
            "messages_processed": {"count": 10.0, "sum": 100.0, "avg": 10.0},
            "tokens_used": {"count": 5.0, "sum": 5000.0, "avg": 1000.0}
        },
        total_tokens=5000,
        total_cost_cents=25.0,
        total_carbon_grams=10.5,
        total_energy_kwh=0.05,
        action_counts={"SPEAK": 50, "THINK": 100},
        error_count=2,
        success_rate=0.98,
        source_node_count=150,
        consolidation_timestamp=datetime.now(timezone.utc),
        raw_data_expired=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        created_by="TSDBConsolidationService",
        updated_by="TSDBConsolidationService",
        type=NodeType.TSDB_SUMMARY,
        id=f"tsdb_summary_{period_start.strftime('%Y%m%d_%H')}",
        scope=GraphScope.LOCAL,
        version=1,
        attributes={}  # Add empty attributes dict
    )
    
    return summary


class TestTSDBRoutes:
    """Test TSDB consolidation API routes."""
    
    def test_get_summaries_success(self, test_client, mock_tsdb_service):
        """Test successful retrieval of TSDB summaries."""
        # Create mock summaries
        now = datetime.now(timezone.utc)
        period1 = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period2 = period1 + timedelta(hours=6)
        
        summary1 = create_mock_tsdb_summary(period1)
        summary2 = create_mock_tsdb_summary(period2)
        
        # Convert to GraphNodes
        node1 = summary1.to_graph_node()
        node2 = summary2.to_graph_node()
        
        # Mock the recall response
        mock_tsdb_service._memory_bus.recall.return_value = [node1, node2]
        
        response = test_client.get(
            "/v1/tsdb/summaries?hours=24",
            headers={"Authorization": "Bearer test_key"}
        )
        
        print(f"Response status: {response.status_code}")
        if response.status_code != 200:
            print(f"Response body: {response.json()}")
        
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["summaries"]) == 2
        assert data["total_count"] == 2
        
        # Verify summary data
        summary = data["summaries"][0]
        assert summary["total_tokens"] == 5000
        assert summary["total_cost_cents"] == 25.0
        assert summary["success_rate"] == 0.98
    
    def test_get_summaries_no_service(self, test_app, mock_auth_observer):
        """Test when TSDB service is not available."""
        # Remove service from app state
        test_app.state.tsdb_consolidation_service = None
        
        # Override auth
        async def mock_get_auth():
            return mock_auth_observer
        
        test_app.dependency_overrides[get_auth_context] = mock_get_auth
        
        client = TestClient(test_app)
        response = client.get(
            "/v1/tsdb/summaries",
            headers={"Authorization": "Bearer test_key"}
        )
        
        assert response.status_code == 503
        assert "TSDB consolidation service not available" in response.json()["detail"]
    
    def test_get_specific_period_success(self, test_client, mock_tsdb_service):
        """Test getting summary for specific period."""
        # Create mock summary
        period_start = datetime(2025, 6, 27, 12, 0, 0, tzinfo=timezone.utc)
        summary = create_mock_tsdb_summary(period_start)
        
        # Mock the service method
        mock_tsdb_service.get_summary_for_period.return_value = summary
        
        response = test_client.get(
            "/v1/tsdb/summaries/20250627_12",
            headers={"Authorization": "Bearer test_key"}
        )
        
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["period_label"] == "2025-06-27-test"
        assert data["total_tokens"] == 5000
    
    def test_get_specific_period_invalid_format(self, test_client):
        """Test invalid period format."""
        response = test_client.get(
            "/v1/tsdb/summaries/invalid",
            headers={"Authorization": "Bearer test_key"}
        )
        
        assert response.status_code == 400
        assert "Invalid period format" in response.json()["detail"]
    
    def test_get_specific_period_invalid_hour(self, test_client):
        """Test invalid consolidation hour."""
        response = test_client.get(
            "/v1/tsdb/summaries/20250627_13",  # 13 is not a valid consolidation hour
            headers={"Authorization": "Bearer test_key"}
        )
        
        assert response.status_code == 400
        assert "Hour must be 00, 06, 12, or 18" in response.json()["detail"]
    
    def test_get_specific_period_not_found(self, test_client, mock_tsdb_service):
        """Test when period summary not found."""
        mock_tsdb_service.get_summary_for_period.return_value = None
        
        response = test_client.get(
            "/v1/tsdb/summaries/20250627_12",
            headers={"Authorization": "Bearer test_key"}
        )
        
        assert response.status_code == 404
        assert "No summary found" in response.json()["detail"]
    
    def test_get_retention_policy(self, test_client):
        """Test getting retention policy information."""
        response = test_client.get(
            "/v1/tsdb/retention",
            headers={"Authorization": "Bearer test_key"}
        )
        
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["raw_retention_hours"] == 24
        assert data["consolidation_interval_hours"] == 6
        assert data["summary_retention"] == "permanent"
        assert "next_consolidation" in data
        assert "last_consolidation" in data
    
    def test_trigger_consolidation_requires_admin(self, test_client):
        """Test that consolidation requires admin role."""
        # test_client has observer role
        response = test_client.post(
            "/v1/tsdb/consolidate",
            json={"force_all": False},
            headers={"Authorization": "Bearer test_key"}
        )
        
        # Should get 403 Forbidden (or 401 depending on auth setup)
        assert response.status_code in [401, 403]
    
    def test_trigger_consolidation_success(self, test_client_admin, mock_tsdb_service):
        """Test successful manual consolidation trigger."""
        # Mock the internal method
        mock_tsdb_service._run_consolidation = AsyncMock()
        
        response = test_client_admin.post(
            "/v1/tsdb/consolidate",
            json={"force_all": False},
            headers={"Authorization": "Bearer test_key"}
        )
        
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "success"
        assert "Consolidation cycle completed" in data["message"]
        mock_tsdb_service._run_consolidation.assert_called_once()
    
    def test_trigger_consolidation_specific_period(self, test_client_admin, mock_tsdb_service):
        """Test consolidating specific period."""
        # Create mock summary
        period_start = datetime(2025, 6, 27, 12, 0, 0, tzinfo=timezone.utc)
        summary = create_mock_tsdb_summary(period_start)
        
        # Mock the internal method
        mock_tsdb_service._force_consolidation = AsyncMock(return_value=summary)
        
        response = test_client_admin.post(
            "/v1/tsdb/consolidate",
            json={
                "force_all": False,
                "period_start": "2025-06-27T12:00:00Z"
            },
            headers={"Authorization": "Bearer test_key"}
        )
        
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "success"
        assert data["periods_processed"] == 1
    
    def test_trigger_consolidation_invalid_period(self, test_client_admin):
        """Test consolidating with invalid period hour."""
        response = test_client_admin.post(
            "/v1/tsdb/consolidate",
            json={
                "force_all": False,
                "period_start": "2025-06-27T13:00:00Z"  # Invalid hour
            },
            headers={"Authorization": "Bearer test_key"}
        )
        
        assert response.status_code == 400
        assert "Period start hour must be" in response.json()["detail"]
    
    @pytest.mark.skip(reason="Auth service not set up in test app")
    def test_no_auth_header(self, test_app):
        """Test request without auth header."""
        # Remove auth override to test actual auth
        test_app.dependency_overrides.clear()
        
        client = TestClient(test_app)
        response = client.get("/v1/tsdb/summaries")
        
        # Should require authentication
        assert response.status_code == 401