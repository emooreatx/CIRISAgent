"""
Unit tests for incident management API endpoints.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.schemas.services.graph.incident import (
    IncidentNode, ProblemNode, IncidentInsightNode,
    IncidentSeverity, IncidentStatus
)
from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphScope
from ciris_engine.api.routes.incidents import (
    IncidentListResponse, PatternListResponse, ProblemListResponse,
    InsightListResponse, RecommendationResponse, AnalyzeRequest
)

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
        line_number=42,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        created_by="system",
        updated_by="system"
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
        last_occurrence=now,
        created_at=now,
        updated_at=now,
        created_by="system",
        updated_by="system"
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
        analysis_timestamp=now,
        created_at=now,
        updated_at=now,
        created_by="IncidentManagementService",
        updated_by="IncidentManagementService"
    )

@pytest.fixture
def mock_services(app):
    """Mock the required services."""
    # Mock incident management service
    incident_service = AsyncMock()
    app.state.incident_management_service = incident_service
    
    # Mock memory service
    memory_service = AsyncMock()
    app.state.memory_service = memory_service
    
    return {
        "incident": incident_service,
        "memory": memory_service
    }

class TestIncidentEndpoints:
    """Test incident management endpoints."""
    
    async def test_get_recent_incidents(self, client, mock_services, sample_incident):
        """Test getting recent incidents."""
        # For now, the endpoint returns empty results
        response = await client.get("/v1/incidents?hours=24")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total"] == 0
        assert data["data"]["incidents"] == []
        assert isinstance(data["data"]["severity_counts"], dict)
        assert isinstance(data["data"]["status_counts"], dict)
    
    async def test_get_incident_details(self, client, mock_services, sample_incident):
        """Test getting specific incident details."""
        # Mock memory service to return incident
        mock_services["memory"].recall_one.return_value = sample_incident.to_graph_node()
        
        response = await client.get("/v1/incidents/incident_001")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == "incident_001"
        assert data["data"]["severity"] == "HIGH"
        assert data["data"]["status"] == "OPEN"
    
    async def test_get_incident_not_found(self, client, mock_services):
        """Test getting non-existent incident."""
        mock_services["memory"].recall_one.return_value = None
        
        response = await client.get("/v1/incidents/nonexistent")
        assert response.status_code == 404
        assert "Incident not found" in response.json()["detail"]
    
    async def test_get_incident_patterns(self, client, mock_services):
        """Test getting incident patterns."""
        response = await client.get("/v1/incidents/patterns?hours=168")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total"] == 0
        assert data["data"]["patterns"] == []
        assert "Last 168 hours" in data["data"]["analysis_period"]
    
    async def test_get_current_problems(self, client, mock_services, sample_problem):
        """Test getting current problems."""
        response = await client.get("/v1/incidents/problems")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total"] == 0
        assert data["data"]["problems"] == []
        assert data["data"]["unresolved_count"] == 0
    
    async def test_get_incident_insights(self, client, mock_services, sample_insight):
        """Test getting incident insights."""
        response = await client.get("/v1/incidents/insights?days=7")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total"] == 0
        assert data["data"]["insights"] == []
        assert data["data"]["applied_count"] == 0
        assert data["data"]["effectiveness_avg"] is None
    
    async def test_analyze_incidents_requires_admin(self, client, mock_services):
        """Test that analyze endpoint requires admin role."""
        # Test with observer token (should fail)
        headers = {"Authorization": "Bearer mock-observer-token"}
        response = await client.post(
            "/v1/incidents/analyze",
            json={"hours": 24},
            headers=headers
        )
        assert response.status_code == 403
    
    async def test_analyze_incidents_success(self, client, mock_services, sample_insight):
        """Test successful incident analysis."""
        mock_services["incident"].process_recent_incidents.return_value = sample_insight
        
        # Use admin token
        headers = {"Authorization": "Bearer mock-admin-token"}
        response = await client.post(
            "/v1/incidents/analyze",
            json={"hours": 24, "force": True},
            headers=headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == "insight_001"
        assert data["data"]["insight_type"] == "PERIODIC_ANALYSIS"
        
        # Verify service was called
        mock_services["incident"].process_recent_incidents.assert_called_once_with(hours=24)
    
    async def test_get_recommendations(self, client, mock_services):
        """Test getting improvement recommendations."""
        response = await client.get("/v1/incidents/recommendations")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["recommendations"]) == 2  # Default example has 2
        assert data["data"]["total_count"] == 4
        
        # Check example recommendation structure
        rec = data["data"]["recommendations"][0]
        assert rec["category"] == "Error Handling"
        assert rec["priority"] == "HIGH"
        assert len(rec["recommendations"]) == 2
        assert rec["rationale"] != ""
    
    async def test_service_unavailable(self, client, app):
        """Test when incident service is not available."""
        # Remove service
        app.state.incident_management_service = None
        
        response = await client.get("/v1/incidents")
        assert response.status_code == 503
        assert "Incident management service not available" in response.json()["detail"]
    
    async def test_memory_service_unavailable(self, client, app, mock_services):
        """Test when memory service is not available."""
        # Remove memory service
        app.state.memory_service = None
        
        response = await client.get("/v1/incidents/incident_001")
        assert response.status_code == 503
        assert "Memory service not available" in response.json()["detail"]
    
    async def test_query_parameters_validation(self, client, mock_services):
        """Test query parameter validation."""
        # Test hours validation
        response = await client.get("/v1/incidents?hours=200")  # Over max
        assert response.status_code == 422
        
        response = await client.get("/v1/incidents?hours=0")  # Under min
        assert response.status_code == 422
        
        # Test analyze hours validation
        headers = {"Authorization": "Bearer mock-admin-token"}
        response = await client.post(
            "/v1/incidents/analyze",
            json={"hours": 200},  # Over max
            headers=headers
        )
        assert response.status_code == 422
    
    async def test_filter_parameters(self, client, mock_services):
        """Test filter parameters are accepted."""
        # Test incident filters
        response = await client.get("/v1/incidents?severity=HIGH&status=OPEN&component=DatabaseService")
        assert response.status_code == 200
        
        # Test problem filters
        response = await client.get("/v1/incidents/problems?status=RESOLVED&min_incidents=5")
        assert response.status_code == 200
        
        # Test recommendation filters
        response = await client.get("/v1/incidents/recommendations?priority=HIGH&category=Performance")
        assert response.status_code == 200