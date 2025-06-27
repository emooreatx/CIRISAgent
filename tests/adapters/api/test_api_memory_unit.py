"""Tests for API memory endpoints."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

from ciris_engine.logic.adapters.api.api_memory import APIMemoryRoutes
from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphScope

class TestAPIMemoryRoutes(AioHTTPTestCase):
    """Test suite for API memory routes."""

    async def get_application(self):
        """Set up test application."""
        self.mock_memory_service = MagicMock()
        # Make async methods actually async and match API implementation
        self.mock_memory_service.list_scopes = AsyncMock()
        self.mock_memory_service.list_entries = AsyncMock()
        self.mock_memory_service.memorize = AsyncMock()
        self.mock_memory_service.search = AsyncMock() 
        self.mock_memory_service.recall = AsyncMock()
        self.mock_memory_service.forget = AsyncMock()
        self.mock_memory_service.get_timeseries = AsyncMock()
        self.mock_memory_service.get_node = AsyncMock()  # Add for node details endpoint
        self.mock_memory_service.get_node_relationships = AsyncMock(return_value=[])  # Add for relationships
        
        # No need for extra setattr calls - already set above
        
        self.mock_bus_manager = MagicMock()
        self.mock_bus_manager.memory_service = self.mock_memory_service
        # Add recall method for agent identity endpoint
        self.mock_bus_manager.recall = AsyncMock()
        
        self.routes = APIMemoryRoutes(self.mock_bus_manager)
        
        app = web.Application()
        self.routes.register(app)
        return app

    async def test_register_routes(self):
        """Test that all memory routes are registered correctly."""
        # Just check that routes are registered by trying to access endpoints
        # This is a simpler approach than inspecting the router
        expected_endpoints = [
            ("GET", "/v1/memory/scopes"),
            ("GET", "/v1/memory/graph/nodes"),
            ("GET", "/v1/memory/graph/search?q=test"),  # search requires query param
            ("GET", "/v1/memory/graph/relationships"),
            ("GET", "/v1/memory/timeseries"),
            ("GET", "/v1/memory/timeline"),
            ("GET", "/v1/memory/identity")
        ]
        
        # Verify routes exist by checking they don't return 404
        for method, path in expected_endpoints:
            resp = await self.client.request(method, path)
            assert resp.status != 404, f"Route {method} {path} not found (got 404)"

    async def test_memory_scopes_success(self):
        """Test successful memory scopes retrieval."""
        expected_scopes = [GraphScope.LOCAL.value, GraphScope.IDENTITY.value]
        self.mock_memory_service.list_scopes = AsyncMock(return_value=expected_scopes)
        
        resp = await self.client.request("GET", "/v1/memory/scopes")
        assert resp.status == 200
        
        data = await resp.json()
        assert "scopes" in data
        assert set(data["scopes"]) == set(expected_scopes)
        self.mock_memory_service.list_scopes.assert_called_once()

    async def test_memory_scopes_fallback(self):
        """Test memory scopes fallback when service unavailable."""
        # Remove memory service to test fallback
        self.mock_bus_manager.memory_service = None
        
        resp = await self.client.request("GET", "/v1/memory/scopes")
        assert resp.status == 200
        
        data = await resp.json()
        assert "scopes" in data
        # Should include all GraphScope enum values as fallback
        expected_scopes = [s.value for s in GraphScope]
        assert set(data["scopes"]) == set(expected_scopes)

    async def test_memory_scopes_error(self):
        """Test memory scopes error handling."""
        self.mock_memory_service.list_scopes = AsyncMock(side_effect=Exception("Database error"))
        
        resp = await self.client.request("GET", "/v1/memory/scopes")
        assert resp.status == 500
        
        data = await resp.json()
        assert "error" in data
        assert "Database error" in data["error"]

    async def test_memory_scope_nodes_success(self):
        """Test successful scope nodes retrieval."""
        mock_nodes = [
            GraphNode(
                id="node1",
                type=NodeType.CONCEPT,
                scope=GraphScope.LOCAL,
                attributes={"content": "Test concept"}
            ),
            GraphNode(
                id="node2",
                type=NodeType.CONCEPT,
                scope=GraphScope.LOCAL,
                attributes={"content": "Test memory"}
            )
        ]
        # API uses list_nodes with filters, not get_nodes_by_scope
        mock_list_nodes = AsyncMock(return_value=mock_nodes)
        self.mock_memory_service.list_nodes = mock_list_nodes
        # Add the local_node_count attribute that the API tries to access
        self.mock_memory_service.local_node_count = 2
        
        resp = await self.client.request("GET", "/v1/memory/scopes/local/nodes")
        if resp.status != 200:
            error_text = await resp.text()
            print(f"Error response: {error_text}")
        assert resp.status == 200
        
        data = await resp.json()
        assert "nodes" in data
        assert len(data["nodes"]) == 2
        assert data["nodes"][0]["id"] == "node1"

    async def test_memory_entries_missing_scope(self):
        """Test memory entries with missing scope parameter."""
        resp = await self.client.request("GET", "/v1/memory/scopes//nodes")
        assert resp.status == 404  # Should not match route

    async def test_graph_nodes_list(self):
        """Test listing graph nodes."""
        # Create mock nodes
        mock_nodes = [
            GraphNode(
                id="node1",
                type=NodeType.AGENT,
                scope=GraphScope.IDENTITY,
                attributes={"name": "test_agent", "content": "Agent identity"}
            ),
            GraphNode(
                id="node2", 
                type=NodeType.CONCEPT,
                scope=GraphScope.LOCAL,
                attributes={"content": "Some knowledge"}
            )
        ]
        
        # Mock the memory service to return nodes - API checks for list_nodes method
        mock_list_nodes = AsyncMock(return_value=mock_nodes)
        self.mock_memory_service.list_nodes = mock_list_nodes
        
        resp = await self.client.request("GET", "/v1/memory/graph/nodes")
        assert resp.status == 200
        
        data = await resp.json()
        assert "nodes" in data
        assert len(data["nodes"]) == 2
        assert data["nodes"][0]["id"] == "node1"

    async def test_graph_search_success(self):
        """Test successful graph search."""
        # Mock search results as dictionaries (as API expects)
        mock_results = [
            {
                "id": "result1",
                "type": "CONCEPT",
                "scope": "local",
                "relevance": 0.95,
                "snippet": "Test content with search term highlighted",
                "attributes": {"content": "Test content with search term"}
            }
        ]
        
        mock_search = AsyncMock(return_value=mock_results)
        self.mock_memory_service.search_graph = mock_search
        
        resp = await self.client.request("GET", "/v1/memory/graph/search?q=search+term")
        assert resp.status == 200
        
        data = await resp.json()
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["id"] == "result1"

    async def test_memory_timeline(self):
        """Test memory timeline endpoint."""
        # Mock timeline entries
        mock_timeline = [
            {
                "timestamp": "2024-01-01T00:00:00Z",
                "node_id": "node1",
                "type": "KNOWLEDGE",
                "content": "Memory from yesterday"
            },
            {
                "timestamp": "2024-01-02T00:00:00Z", 
                "node_id": "node2",
                "type": "ACTION",
                "content": "Action taken today"
            }
        ]
        
        mock_get_timeline = AsyncMock(return_value=mock_timeline)
        self.mock_memory_service.get_timeline = mock_get_timeline
        
        resp = await self.client.request("GET", "/v1/memory/timeline?hours=24")
        assert resp.status == 200
        
        data = await resp.json()
        assert "timeline" in data
        assert len(data["timeline"]) == 2
        assert data["timeline"][0]["node_id"] == "node1"  # Fixed: should be node_id not id

    async def test_node_details(self):
        """Test getting node details."""
        # Mock a specific node
        mock_node = GraphNode(
            id="test123",
            type=NodeType.AGENT,
            scope=GraphScope.IDENTITY,
            attributes={"purpose": "help users", "created": "2024-01-01", "content": "Agent purpose and values"}
        )
        
        # The issue is that get_node is already set to AsyncMock in get_application, 
        # just configure its return value
        self.mock_memory_service.get_node.return_value = mock_node
        
        resp = await self.client.request("GET", "/v1/memory/graph/nodes/test123")
        assert resp.status == 200
        
        data = await resp.json()
        assert "node" in data
        assert data["node"]["id"] == "test123"
        assert data["node"]["type"] == "agent"  # Enum value is lowercase
        assert data["node"]["attributes"]["purpose"] == "help users"

    async def test_memory_relationships(self):
        """Test getting memory relationships."""
        # Mock relationships/edges
        mock_relationships = [
            {
                "source_id": "node1",
                "target_id": "node2",
                "relationship_type": "RELATES_TO",
                "attributes": {"strength": 0.8}
            },
            {
                "source_id": "node1",
                "target_id": "node3",
                "relationship_type": "DERIVED_FROM",
                "attributes": {"confidence": 0.9}
            }
        ]
        
        mock_list_relationships = AsyncMock(return_value=mock_relationships)
        self.mock_memory_service.list_relationships = mock_list_relationships
        
        resp = await self.client.request("GET", "/v1/memory/graph/relationships")
        assert resp.status == 200
        
        data = await resp.json()
        assert "relationships" in data
        assert len(data["relationships"]) == 2
        assert data["relationships"][0]["source_id"] == "node1"  # Fixed: should be source_id not source

    async def test_agent_identity(self):
        """Test getting agent identity."""
        # Mock identity node
        mock_identity = GraphNode(
            id="AGENT_IDENTITY",
            type=NodeType.AGENT,
            scope=GraphScope.IDENTITY,
            attributes={
                "agent_id": "test-agent-123",
                "name": "CIRIS", 
                "purpose": "help users ethically", 
                "created_at": "2025-01-01T00:00:00Z",
                "capabilities": ["speak", "memorize", "recall"],
                "variance_threshold": 0.2
            }
        )
        
        # Mock the recall result that the API expects
        mock_result = MagicMock()
        mock_result.nodes = [mock_identity]
        self.mock_bus_manager.recall.return_value = mock_result
        
        resp = await self.client.request("GET", "/v1/memory/identity")
        assert resp.status == 200
        
        data = await resp.json()
        assert "identity" in data
        assert data["identity"]["name"] == "CIRIS"
        assert data["identity"]["agent_id"] == "test-agent-123"

    async def test_memory_timeseries_success(self):
        """Test successful memory timeseries retrieval."""
        mock_timeseries = {
            "timeline": [
                {"timestamp": "2024-01-01T00:00:00Z", "event": "memory_created", "node_id": "node1"},
                {"timestamp": "2024-01-01T01:00:00Z", "event": "memory_accessed", "node_id": "node1"}
            ],
            "total_events": 2
        }
        self.mock_memory_service.get_timeseries = AsyncMock(return_value=mock_timeseries)
        
        resp = await self.client.request("GET", "/v1/memory/timeseries?scope=session&limit=100")
        assert resp.status == 200
        
        data = await resp.json()
        assert "timeline" in data
        assert "total_events" in data
        assert data["total_events"] == 2
        assert len(data["timeline"]) == 2
        self.mock_memory_service.get_timeseries.assert_called_once()

    async def test_memory_service_unavailable(self):
        """Test behavior when memory service is completely unavailable."""
        # Remove memory service
        delattr(self.mock_bus_manager, 'memory_service')
        
        resp = await self.client.request("GET", "/v1/memory/graph/nodes")
        assert resp.status == 503  # Should return service unavailable
        
        data = await resp.json()
        assert "error" in data
        assert "Memory service not available" in data["error"]

    async def test_concurrent_memory_operations(self):
        """Test handling of concurrent memory operations."""
        # Mock all the methods that might be called
        self.mock_memory_service.list_nodes = AsyncMock(return_value=[])
        self.mock_memory_service.search_graph = AsyncMock(return_value=[])
        self.mock_memory_service.list_scopes = AsyncMock(return_value=["local", "identity"])
        
        # Test concurrent read operations
        import asyncio
        
        # Make concurrent GET requests to different endpoints
        nodes_task = self.client.request("GET", "/v1/memory/graph/nodes")
        search_task = self.client.request("GET", "/v1/memory/graph/search?q=test")
        scopes_task = self.client.request("GET", "/v1/memory/scopes")
        
        nodes_resp, search_resp, scopes_resp = await asyncio.gather(
            nodes_task, search_task, scopes_task
        )
        
        # All should succeed
        assert nodes_resp.status == 200
        assert search_resp.status == 200  
        assert scopes_resp.status == 200