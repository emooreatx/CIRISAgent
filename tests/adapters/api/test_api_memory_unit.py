"""Tests for API memory endpoints."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from ciris_engine.adapters.api.api_memory import APIMemoryRoutes
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpStatus


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
        
        # Add hasattr checks that the API does
        self.mock_memory_service.list_scopes = AsyncMock()
        setattr(self.mock_memory_service, 'list_scopes', self.mock_memory_service.list_scopes)
        setattr(self.mock_memory_service, 'list_entries', self.mock_memory_service.list_entries)
        
        self.mock_sink = MagicMock()
        self.mock_sink.memory_service = self.mock_memory_service
        
        self.routes = APIMemoryRoutes(self.mock_sink)
        
        app = web.Application()
        self.routes.register(app)
        return app

    @unittest_run_loop
    async def test_register_routes(self):
        """Test that all memory routes are registered correctly."""
        # Just check that routes are registered by trying to access endpoints
        # This is a simpler approach than inspecting the router
        expected_endpoints = [
            ("GET", "/v1/memory/scopes"),
            ("GET", "/v1/memory/test/entries"),
            ("POST", "/v1/memory/test/store"),
            ("POST", "/v1/memory/search"),
            ("POST", "/v1/memory/recall"),
            ("DELETE", "/v1/memory/test/node123"),
            ("GET", "/v1/memory/timeseries")
        ]
        
        # Verify routes exist by checking they don't return 404
        for method, path in expected_endpoints:
            resp = await self.client.request(method, path)
            assert resp.status != 404, f"Route {method} {path} not found (got 404)"

    @unittest_run_loop
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

    @unittest_run_loop
    async def test_memory_scopes_fallback(self):
        """Test memory scopes fallback when service unavailable."""
        # Remove memory service to test fallback
        self.mock_sink.memory_service = None
        
        resp = await self.client.request("GET", "/v1/memory/scopes")
        assert resp.status == 200
        
        data = await resp.json()
        assert "scopes" in data
        # Should include all GraphScope enum values as fallback
        expected_scopes = [s.value for s in GraphScope]
        assert set(data["scopes"]) == set(expected_scopes)

    @unittest_run_loop
    async def test_memory_scopes_error(self):
        """Test memory scopes error handling."""
        self.mock_memory_service.list_scopes = AsyncMock(side_effect=Exception("Database error"))
        
        resp = await self.client.request("GET", "/v1/memory/scopes")
        assert resp.status == 500
        
        data = await resp.json()
        assert "error" in data
        assert "Database error" in data["error"]

    @unittest_run_loop
    async def test_memory_entries_success(self):
        """Test successful memory entries retrieval."""
        mock_entries = [
            {"id": "node1", "type": NodeType.CONCEPT.value, "content": "Test concept"},
            {"id": "node2", "type": NodeType.CONCEPT.value, "content": "Test memory"}
        ]
        self.mock_memory_service.list_entries = AsyncMock(return_value=mock_entries)
        
        resp = await self.client.request("GET", "/v1/memory/session/entries")
        assert resp.status == 200
        
        data = await resp.json()
        assert "entries" in data
        assert len(data["entries"]) == 2
        assert data["entries"][0]["id"] == "node1"
        self.mock_memory_service.list_entries.assert_called_once_with("session")

    @unittest_run_loop
    async def test_memory_entries_missing_scope(self):
        """Test memory entries with missing scope parameter."""
        resp = await self.client.request("GET", "/v1/memory//entries")
        assert resp.status == 404  # Should not match route

    @unittest_run_loop
    async def test_memory_store_success(self):
        """Test successful memory storage."""
        payload = {
            "key": "test_key",
            "value": "Test memory content"
        }
        
        from ciris_engine.schemas.memory_schemas_v1 import MemoryOpResult
        mock_result = MemoryOpResult(status=MemoryOpStatus.OK, reason=None)
        self.mock_sink.memorize = AsyncMock(return_value=mock_result)
        
        resp = await self.client.request("POST", "/v1/memory/session/store",
                                       data=json.dumps(payload),
                                       headers={"Content-Type": "application/json"})
        assert resp.status == 200
        
        data = await resp.json()
        assert data["result"] == "ok"
        self.mock_sink.memorize.assert_called_once()

    @unittest_run_loop
    async def test_memory_store_invalid_json(self):
        """Test memory store with invalid JSON."""
        resp = await self.client.request("POST", "/v1/memory/session/store",
                                       data="invalid json",
                                       headers={"Content-Type": "application/json"})
        assert resp.status == 400

    @unittest_run_loop
    async def test_memory_search_success(self):
        """Test successful memory search."""
        payload = {
            "query": "test concept",
            "scope": GraphScope.LOCAL.value,
            "limit": 10
        }
        
        mock_results = [
            {"id": "node1", "content": "Test concept", "relevance": 0.9},
            {"id": "node2", "content": "Another concept", "relevance": 0.7}
        ]
        self.mock_memory_service.search = AsyncMock(return_value=mock_results)
        
        resp = await self.client.request("POST", "/v1/memory/search",
                                       data=json.dumps(payload),
                                       headers={"Content-Type": "application/json"})
        assert resp.status == 200
        
        data = await resp.json()
        assert "results" in data
        assert len(data["results"]) == 2
        assert data["results"][0]["relevance"] == 0.9
        self.mock_memory_service.search.assert_called_once()

    @unittest_run_loop
    async def test_memory_recall_success(self):
        """Test successful memory recall."""
        payload = {
            "context": "discussing AI concepts",
            "scope": GraphScope.IDENTITY.value,
            "max_results": 5
        }
        
        mock_memories = [
            {"id": "memory1", "content": "Previous AI discussion", "timestamp": "2024-01-01"},
            {"id": "memory2", "content": "Related concept", "timestamp": "2024-01-02"}
        ]
        self.mock_memory_service.recall = AsyncMock(return_value=mock_memories)
        
        resp = await self.client.request("POST", "/v1/memory/recall",
                                       data=json.dumps(payload),
                                       headers={"Content-Type": "application/json"})
        assert resp.status == 200
        
        data = await resp.json()
        assert "memories" in data
        assert len(data["memories"]) == 2
        assert data["memories"][0]["id"] == "memory1"
        self.mock_memory_service.recall.assert_called_once()

    @unittest_run_loop
    async def test_memory_forget_success(self):
        """Test successful memory deletion."""
        mock_result = {"status": MemoryOpStatus.OK.value, "deleted": True}
        self.mock_memory_service.forget = AsyncMock(return_value=mock_result)
        
        resp = await self.client.request("DELETE", "/v1/memory/session/node123")
        assert resp.status == 200
        
        data = await resp.json()
        assert data["status"] == MemoryOpStatus.OK.value
        assert data["deleted"] is True
        self.mock_memory_service.forget.assert_called_once_with("session", "node123")

    @unittest_run_loop
    async def test_memory_forget_not_found(self):
        """Test memory deletion when node not found."""
        mock_result = {"status": MemoryOpStatus.ERROR.value, "deleted": False}
        self.mock_memory_service.forget = AsyncMock(return_value=mock_result)
        
        resp = await self.client.request("DELETE", "/v1/memory/session/nonexistent")
        assert resp.status == 200
        
        data = await resp.json()
        assert data["status"] == MemoryOpStatus.ERROR.value
        assert data["deleted"] is False

    @unittest_run_loop
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

    @unittest_run_loop
    async def test_memory_service_unavailable(self):
        """Test behavior when memory service is completely unavailable."""
        # Remove memory service
        delattr(self.mock_sink, 'memory_service')
        
        resp = await self.client.request("GET", "/v1/memory/session/entries")
        assert resp.status == 500
        
        data = await resp.json()
        assert "error" in data

    @unittest_run_loop
    async def test_concurrent_memory_operations(self):
        """Test handling of concurrent memory operations."""
        # Setup concurrent calls - use the existing memorize method
        from ciris_engine.schemas.memory_schemas_v1 import MemoryOpResult
        mock_result = MemoryOpResult(status=MemoryOpStatus.OK, reason=None)
        self.mock_sink.memorize = AsyncMock(return_value=mock_result)
        self.mock_memory_service.search = AsyncMock(return_value=[{"id": "node1", "relevance": 0.9}])
        
        # Make concurrent requests
        store_payload = {"key": "test_key", "value": "Test"}
        search_payload = {"query": "test", "scope": GraphScope.LOCAL.value}
        
        import asyncio
        store_task = self.client.request("POST", "/v1/memory/session/store",
                                       data=json.dumps(store_payload),
                                       headers={"Content-Type": "application/json"})
        search_task = self.client.request("POST", "/v1/memory/search",
                                        data=json.dumps(search_payload),
                                        headers={"Content-Type": "application/json"})
        
        store_resp, search_resp = await asyncio.gather(store_task, search_task)
        
        assert store_resp.status == 200
        assert search_resp.status == 200
        
        # Verify both service methods were called
        self.mock_sink.memorize.assert_called_once()
        self.mock_memory_service.search.assert_called_once()