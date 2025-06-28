"""
Test simplified memory endpoints for API v3.

Tests the consolidated MEMORIZE, RECALL, FORGET pattern.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock
from fastapi.testclient import TestClient

from ciris_engine.api.app import create_app
from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphScope
from ciris_engine.schemas.services.operations import MemoryOpResult, MemoryOpStatus
from ciris_engine.schemas.api.auth import UserRole


@pytest.fixture
def mock_memory_service():
    """Mock memory service with common operations."""
    service = AsyncMock()
    
    # Sample nodes for testing
    sample_nodes = [
        GraphNode(
            id="test_node_1",
            type=NodeType.CONCEPT,
            scope=GraphScope.LOCAL,
            attributes={
                "name": "Test Concept",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "tags": ["test", "concept"]
            }
        ),
        GraphNode(
            id="test_node_2", 
            type=NodeType.OBSERVATION,
            scope=GraphScope.LOCAL,
            attributes={
                "name": "Test Observation",
                "created_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
                "tags": ["test", "observation"]
            }
        )
    ]
    
    # Mock memorize
    service.memorize.return_value = MemoryOpResult(
        status=MemoryOpStatus.OK,
        reason="Node stored successfully"
    )
    
    # Mock recall
    service.recall.return_value = sample_nodes
    
    # Mock forget
    service.forget.return_value = MemoryOpResult(
        status=MemoryOpStatus.OK,
        reason="Node forgotten successfully"
    )
    
    # Mock search
    service.search.return_value = sample_nodes
    
    return service


@pytest.fixture
def test_app(mock_memory_service, mock_auth_service):
    """Create test app with mocked services."""
    app = create_app()
    
    # Set up app state with mock services
    app.state.memory_service = mock_memory_service
    app.state.auth_service = mock_auth_service
    
    # Mock other required services for app initialization
    app.state.time_service = Mock()
    app.state.time_service.now = Mock(return_value=datetime.now(timezone.utc))
    
    return app


@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)


class TestMemoryStore:
    """Test POST /v1/memory/store endpoint."""
    
    def test_store_memory_success(self, client, mock_memory_service, admin_headers):
        """Test successful memory storage."""
        # Arrange
        node = GraphNode(
            id="new_node",
            type=NodeType.CONCEPT,
            scope=GraphScope.LOCAL,
            attributes={"name": "New Concept"}
        )
        
        # Act
        response = client.post(
            "/v1/memory/store",
            json={"node": node.model_dump()},
            headers=admin_headers
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "ok"
        assert data["data"]["reason"] == "Node stored successfully"
        mock_memory_service.memorize.assert_called_once()
    
    def test_store_memory_requires_admin(self, client, observer_headers):
        """Test that storing memories requires ADMIN role."""
        # Arrange
        node = GraphNode(
            id="new_node",
            type=NodeType.CONCEPT,
            scope=GraphScope.LOCAL,
            attributes={"name": "New Concept"}
        )
        
        # Act
        response = client.post(
            "/v1/memory/store",
            json={"node": node.model_dump()},
            headers=observer_headers
        )
        
        # Assert
        assert response.status_code == 403


class TestMemoryQuery:
    """Test POST /v1/memory/query endpoint."""
    
    def test_query_by_id(self, client, mock_memory_service, observer_headers):
        """Test querying memory by node ID."""
        # Act
        response = client.post(
            "/v1/memory/query",
            json={"node_id": "test_node_1"},
            headers=observer_headers
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        assert data["data"][0]["id"] == "test_node_1"
    
    def test_query_by_text(self, client, mock_memory_service, observer_headers):
        """Test text-based memory search."""
        # Act
        response = client.post(
            "/v1/memory/query",
            json={"query": "quantum computing"},
            headers=observer_headers
        )
        
        # Assert
        assert response.status_code == 200
        mock_memory_service.search.assert_called_once()
    
    def test_query_by_type(self, client, mock_memory_service, observer_headers):
        """Test querying by node type."""
        # Act
        response = client.post(
            "/v1/memory/query",
            json={"type": "concept"},
            headers=observer_headers
        )
        
        # Assert  
        assert response.status_code == 200
        mock_memory_service.recall.assert_called()
    
    def test_query_with_time_filter(self, client, mock_memory_service, observer_headers):
        """Test querying with time filters."""
        # Arrange
        since = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        until = datetime.now(timezone.utc).isoformat()
        
        # Act
        response = client.post(
            "/v1/memory/query",
            json={
                "type": "observation",
                "since": since,
                "until": until
            },
            headers=observer_headers
        )
        
        # Assert
        assert response.status_code == 200
        # Should filter nodes by time
    
    def test_query_related_nodes(self, client, mock_memory_service, observer_headers):
        """Test finding related nodes."""
        # Act
        response = client.post(
            "/v1/memory/query",
            json={"related_to": "test_node_1"},
            headers=observer_headers
        )
        
        # Assert
        assert response.status_code == 200
        mock_memory_service.recall.assert_called()
        # Should return nodes except the source
    
    def test_query_requires_params(self, client, observer_headers):
        """Test that query requires at least one parameter."""
        # Act
        response = client.post(
            "/v1/memory/query",
            json={},
            headers=observer_headers
        )
        
        # Assert
        assert response.status_code == 422


class TestMemoryDelete:
    """Test DELETE /v1/memory/{id} endpoint."""
    
    def test_forget_memory_success(self, client, mock_memory_service, admin_headers):
        """Test successful memory deletion."""
        # Act
        response = client.delete(
            "/v1/memory/test_node_1",
            headers=admin_headers
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "ok"
        mock_memory_service.forget.assert_called_once()
    
    def test_forget_memory_not_found(self, client, mock_memory_service, admin_headers):
        """Test deleting non-existent memory."""
        # Arrange
        mock_memory_service.recall.return_value = []
        
        # Act
        response = client.delete(
            "/v1/memory/nonexistent",
            headers=admin_headers
        )
        
        # Assert
        assert response.status_code == 404
    
    def test_forget_requires_admin(self, client, observer_headers):
        """Test that forgetting memories requires ADMIN role."""
        # Act
        response = client.delete(
            "/v1/memory/test_node_1",
            headers=observer_headers
        )
        
        # Assert
        assert response.status_code == 403


class TestMemoryGet:
    """Test GET /v1/memory/{id} endpoint."""
    
    def test_get_memory_by_id(self, client, mock_memory_service, observer_headers):
        """Test getting specific memory by ID."""
        # Act
        response = client.get(
            "/v1/memory/test_node_1",
            headers=observer_headers
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["id"] == "test_node_1"
    
    def test_get_memory_not_found(self, client, mock_memory_service, observer_headers):
        """Test getting non-existent memory."""
        # Arrange
        mock_memory_service.recall.return_value = []
        
        # Act
        response = client.get(
            "/v1/memory/nonexistent",
            headers=observer_headers
        )
        
        # Assert
        assert response.status_code == 404


class TestMemoryTimeline:
    """Test GET /v1/memory/timeline endpoint."""
    
    def test_timeline_view(self, client, mock_memory_service, observer_headers):
        """Test temporal view of memories."""
        # Act
        response = client.get(
            "/v1/memory/timeline?hours=24",
            headers=observer_headers
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "memories" in data["data"]
        assert "buckets" in data["data"]
        assert "start_time" in data["data"]
        assert "end_time" in data["data"]
        assert "total" in data["data"]
    
    def test_timeline_with_filters(self, client, mock_memory_service, observer_headers):
        """Test timeline with type and scope filters."""
        # Act
        response = client.get(
            "/v1/memory/timeline?hours=48&type=observation&scope=local",
            headers=observer_headers
        )
        
        # Assert
        assert response.status_code == 200
        # Should apply filters
    
    def test_timeline_bucket_sizes(self, client, mock_memory_service, observer_headers):
        """Test different bucket sizes for timeline."""
        # Test hourly buckets
        response = client.get(
            "/v1/memory/timeline?hours=24&bucket_size=hour",
            headers=observer_headers
        )
        assert response.status_code == 200
        
        # Test daily buckets
        response = client.get(
            "/v1/memory/timeline?hours=168&bucket_size=day",
            headers=observer_headers
        )
        assert response.status_code == 200