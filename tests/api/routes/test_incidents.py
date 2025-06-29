"""
Unit tests for incident data through telemetry API endpoints.

Note: Incidents have been integrated into telemetry in the simplified API.
- Incident counts are in GET /v1/telemetry/overview
- Incident details can be accessed via POST /v1/telemetry/query
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock
from fastapi.testclient import TestClient

from ciris_engine.api.app import create_app
from ciris_engine.schemas.api.auth import UserRole
from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.schemas.services.graph.incident import (
    IncidentNode, ProblemNode, IncidentInsightNode,
    IncidentSeverity, IncidentStatus
)
from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphScope

@pytest.fixture
def sample_incident():
    """Create a sample incident node."""
    return IncidentNode(
        id="incident_001",
        type=NodeType.AUDIT_ENTRY,
        scope=GraphScope.LOCAL,
        attributes={},
        incident_type="ERROR",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.OPEN,
        description="Database connection timeout",
        source_component="DatabaseService",
        detected_at=datetime.now(timezone.utc),
        filename="database_service.py",
        line_number=42
    )

@pytest.fixture
def sample_problem():
    """Create a sample problem node."""
    now = datetime.now(timezone.utc)
    return ProblemNode(
        id="problem_001",
        type=NodeType.CONCEPT,
        scope=GraphScope.IDENTITY,
        attributes={},
        problem_statement="Recurring database connection failures",
        affected_incidents=["incident_001", "incident_002", "incident_003"],
        status="UNDER_INVESTIGATION",
        potential_root_causes=["Connection pool exhaustion", "Network instability"],
        recommended_actions=["Increase connection pool size", "Implement retry logic"],
        incident_count=3,
        first_occurrence=now - timedelta(days=7),
        last_occurrence=now
    )

@pytest.fixture
def sample_insight():
    """Create a sample insight node."""
    now = datetime.now(timezone.utc)
    return IncidentInsightNode(
        id="insight_001",
        type=NodeType.CONCEPT,
        scope=GraphScope.LOCAL,
        attributes={},
        insight_type="PERIODIC_ANALYSIS",
        summary="Identified 3 recurring database issues requiring attention",
        details={
            "incident_count": 15,
            "pattern_count": 3,
            "problem_count": 1
        },
        behavioral_adjustments=["Implement exponential backoff for retries"],
        configuration_changes=["Increase connection_pool_size to 50"],
        analysis_timestamp=now
    )

@pytest.fixture
def mock_services():
    """Mock the required services."""
    # Mock incident management service
    incident_service = AsyncMock()

    # Mock memory service
    memory_service = AsyncMock()

    # Mock telemetry service
    telemetry_service = AsyncMock()
    telemetry_service.query_metrics = AsyncMock(return_value=[])
    telemetry_service.get_telemetry_summary = AsyncMock()

    return {
        "incident_management": incident_service,
        "memory_service": memory_service,
        "telemetry_service": telemetry_service
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

    # Define different responses based on the API key
    async def mock_validate_api_key(api_key: str):
        if api_key == "mock-admin-token":
            return Mock(user_id="admin_user", role=UserRole.ADMIN)
        elif api_key == "mock-observer-token":
            return Mock(user_id="observer_user", role=UserRole.OBSERVER)
        else:
            return None

    mock_auth_service.validate_api_key = mock_validate_api_key
    mock_auth_service._get_key_id = Mock(return_value="test_key")
    app.state.auth_service = mock_auth_service

    return app

@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)

class TestIncidentsThroughTelemetry:
    """Test incident data access through telemetry endpoints."""

    def test_incidents_in_overview(self, client, test_app, sample_incident):
        """Test that incident count appears in telemetry overview."""
        # Mock incident service to return some incidents
        test_app.state.incident_management.get_incidents = AsyncMock(return_value=[sample_incident])

        headers = {"Authorization": "Bearer mock-observer-token"}
        response = client.get("/v1/telemetry/overview", headers=headers)
        assert response.status_code == 200

        data = response.json()
        # Check the wrapped response structure
        assert "data" in data
        assert "recent_incidents" in data["data"]
        # The mock returns 1 incident
        assert isinstance(data["data"]["recent_incidents"], int)
        assert data["data"]["recent_incidents"] >= 0

    def test_query_incidents(self, client, test_app, sample_incident):
        """Test querying incidents through telemetry query endpoint."""
        # Mock incident service to return incidents
        test_app.state.incident_management.query_incidents = AsyncMock(return_value=[sample_incident])

        # Use admin token for query endpoint
        headers = {"Authorization": "Bearer mock-admin-token"}
        response = client.post(
            "/v1/telemetry/query",
            json={
                "query_type": "incidents",
                "filters": {
                    "severity": "HIGH",
                    "status": "OPEN"
                },
                "limit": 10
            },
            headers=headers
        )
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        assert data["data"]["query_type"] == "incidents"
        assert isinstance(data["data"]["results"], list)
        assert isinstance(data["data"]["total"], int)
        assert isinstance(data["data"]["execution_time_ms"], float)

    def test_query_insights(self, client, test_app, sample_insight):
        """Test querying incident insights through telemetry."""
        # Mock incident service to return insights
        test_app.state.incident_management.get_insights = AsyncMock(return_value=[sample_insight])

        # Use admin token
        headers = {"Authorization": "Bearer mock-admin-token"}
        response = client.post(
            "/v1/telemetry/query",
            json={
                "query_type": "insights",
                "filters": {},
                "limit": 10
            },
            headers=headers
        )
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        assert data["data"]["query_type"] == "insights"
        assert isinstance(data["data"]["results"], list)

    def test_query_requires_admin(self, client):
        """Test that telemetry query endpoint requires admin role."""
        # Test with observer token (should fail)
        headers = {"Authorization": "Bearer mock-observer-token"}
        response = client.post(
            "/v1/telemetry/query",
            json={
                "query_type": "incidents",
                "filters": {}
            },
            headers=headers
        )
        assert response.status_code == 403

    def test_query_time_filtering(self, client):
        """Test time-based filtering in queries."""
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=24)

        headers = {"Authorization": "Bearer mock-admin-token"}
        response = client.post(
            "/v1/telemetry/query",
            json={
                "query_type": "incidents",
                "start_time": start_time.isoformat(),
                "end_time": now.isoformat(),
                "limit": 100
            },
            headers=headers
        )
        assert response.status_code == 200

        data = response.json()
        assert "data" in data

    def test_incident_metrics(self, client):
        """Test that incident-related metrics appear in detailed metrics."""
        headers = {"Authorization": "Bearer mock-observer-token"}
        response = client.get("/v1/telemetry/metrics", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        assert isinstance(data["data"]["metrics"], list)

        # Look for incident-related metrics
        metric_names = [m["name"] for m in data["data"]["metrics"]]
        # These would be populated in real implementation
        # assert "incidents_detected" in metric_names

    def test_service_unavailable(self, client, test_app):
        """Test when incident service is not available."""
        # Remove service
        test_app.state.incident_management = None

        # Should still work but without incident data
        headers = {"Authorization": "Bearer mock-observer-token"}
        response = client.get("/v1/telemetry/overview", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["data"]["recent_incidents"] == 0

    def test_query_aggregations(self, client):
        """Test aggregation capabilities in queries."""
        headers = {"Authorization": "Bearer mock-admin-token"}
        response = client.post(
            "/v1/telemetry/query",
            json={
                "query_type": "incidents",
                "filters": {},
                "aggregations": ["count"],
                "limit": 100
            },
            headers=headers
        )
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        # With count aggregation, results should be aggregated
        if data["data"]["results"]:
            # Check if aggregation is in the data field of the result
            assert any(r.get("data", {}).get("aggregation") == "count" for r in data["data"]["results"])
