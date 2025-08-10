"""
Comprehensive tests for memory API routes.

Tests all endpoints in /v1/memory/* to improve coverage from 11.5%.
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from ciris_engine.logic.adapters.api.app import create_app
from ciris_engine.schemas.services.graph_core import GraphNode, GraphScope, NodeType
from ciris_engine.schemas.services.operations import MemoryOpResult, MemoryQuery


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Get auth headers for testing."""
    return {"Authorization": "Bearer admin:ciris_admin_password"}


@pytest.fixture
def mock_memory_service():
    """Mock memory service."""
    with patch("ciris_engine.logic.adapters.api.routes.memory.get_memory_service") as mock_get:
        mock_service = MagicMock()
        mock_service.memorize = AsyncMock()
        mock_service.recall = AsyncMock()
        mock_service.forget = AsyncMock()
        mock_service.query = AsyncMock()
        mock_service.get_timeline = AsyncMock()
        mock_service.update_memory = AsyncMock()
        mock_get.return_value = mock_service
        yield mock_service


class TestMemoryRoutes:
    """Test memory API endpoints."""

    def test_store_memory_success(self, client, auth_headers, mock_memory_service):
        """Test successful memory storage."""
        # Setup mock response
        memory_id = str(uuid4())
        mock_memory_service.memorize.return_value = MemoryOpResult(
            status="ok", data=memory_id, message="Memory stored successfully"
        )

        response = client.post(
            "/v1/memory/store",
            headers=auth_headers,
            json={
                "content": "Important fact to remember",
                "tags": ["important", "fact"],
                "metadata": {"source": "user_input", "confidence": 0.95},
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["memory_id"] == memory_id
        assert data["message"] == "Memory stored successfully"

    def test_store_memory_no_auth(self, client):
        """Test that store memory requires authentication."""
        response = client.post("/v1/memory/store", json={"content": "Should fail without auth"})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_store_memory_invalid_content(self, client, auth_headers):
        """Test storing memory with invalid content."""
        response = client.post(
            "/v1/memory/store", headers=auth_headers, json={"content": "", "tags": ["test"]}  # Empty content
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_recall_memory_by_id(self, client, auth_headers, mock_memory_service):
        """Test recalling memory by ID."""
        memory_id = str(uuid4())
        mock_node = GraphNode(
            id=memory_id,
            type=NodeType.OBSERVATION,
            scope=GraphScope.LOCAL,
            attributes={"content": "Recalled memory content", "timestamp": datetime.now(timezone.utc).isoformat()},
        )
        mock_memory_service.recall.return_value = [mock_node]

        response = client.get(f"/v1/memory/{memory_id}", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == memory_id
        assert "Recalled memory content" in str(data["data"])

    def test_recall_memory_not_found(self, client, auth_headers, mock_memory_service):
        """Test recalling non-existent memory."""
        mock_memory_service.recall.return_value = []

        response = client.get(f"/v1/memory/{uuid4()}", headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["message"].lower()

    def test_query_memories(self, client, auth_headers, mock_memory_service):
        """Test querying memories with filters."""
        # Setup mock results
        mock_nodes = [
            GraphNode(
                id=str(uuid4()),
                type=NodeType.OBSERVATION,
                scope=GraphScope.LOCAL,
                attributes={"content": f"Memory {i}"},
            )
            for i in range(3)
        ]
        mock_memory_service.query.return_value = mock_nodes

        response = client.post(
            "/v1/memory/query",
            headers=auth_headers,
            json={
                "query": "test query",
                "filters": {
                    "tags": ["important"],
                    "date_from": "2024-01-01T00:00:00Z",
                    "date_to": "2024-12-31T23:59:59Z",
                },
                "limit": 10,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["memories"]) == 3
        assert data["data"]["total_count"] == 3

    def test_query_memories_empty_result(self, client, auth_headers, mock_memory_service):
        """Test query with no results."""
        mock_memory_service.query.return_value = []

        response = client.post("/v1/memory/query", headers=auth_headers, json={"query": "nonexistent", "limit": 10})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["memories"]) == 0

    def test_delete_memory(self, client, auth_headers, mock_memory_service):
        """Test deleting a memory."""
        memory_id = str(uuid4())
        mock_memory_service.forget.return_value = MemoryOpResult(
            status="ok", data=True, message="Memory deleted successfully"
        )

        response = client.delete(f"/v1/memory/{memory_id}", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Memory deleted successfully"

    def test_delete_memory_not_found(self, client, auth_headers, mock_memory_service):
        """Test deleting non-existent memory."""
        mock_memory_service.forget.return_value = MemoryOpResult(status="error", data=False, message="Memory not found")

        response = client.delete(f"/v1/memory/{uuid4()}", headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_memory(self, client, auth_headers, mock_memory_service):
        """Test updating an existing memory."""
        memory_id = str(uuid4())
        mock_memory_service.update_memory.return_value = MemoryOpResult(
            status="ok", data=memory_id, message="Memory updated successfully"
        )

        response = client.put(
            f"/v1/memory/{memory_id}",
            headers=auth_headers,
            json={
                "content": "Updated memory content",
                "tags": ["updated"],
                "metadata": {"last_modified": datetime.now(timezone.utc).isoformat()},
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Memory updated successfully"

    def test_get_memory_timeline(self, client, auth_headers, mock_memory_service):
        """Test getting memory timeline."""
        # Create timeline entries
        timeline_entries = [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "observation",
                "content": "User said hello",
                "memory_id": str(uuid4()),
            },
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "task",
                "content": "Responded with greeting",
                "memory_id": str(uuid4()),
            },
        ]
        mock_memory_service.get_timeline.return_value = timeline_entries

        response = client.get(
            "/v1/memory/timeline", headers=auth_headers, params={"hours": 24, "event_types": ["observation", "task"]}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["timeline"]) == 2
        assert data["data"]["timeline"][0]["event_type"] == "observation"

    def test_memory_search_semantic(self, client, auth_headers, mock_memory_service):
        """Test semantic search in memories."""
        # Mock semantic search results
        mock_results = [
            {
                "memory_id": str(uuid4()),
                "content": "Related memory about cats",
                "similarity_score": 0.92,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            {
                "memory_id": str(uuid4()),
                "content": "Another memory about pets",
                "similarity_score": 0.85,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        ]
        mock_memory_service.semantic_search = AsyncMock(return_value=mock_results)

        response = client.post(
            "/v1/memory/search",
            headers=auth_headers,
            json={"query": "Tell me about cats", "semantic": True, "threshold": 0.8, "limit": 5},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["results"]) == 2
        assert data["data"]["results"][0]["similarity_score"] > data["data"]["results"][1]["similarity_score"]

    def test_bulk_store_memories(self, client, auth_headers, mock_memory_service):
        """Test storing multiple memories at once."""
        memory_ids = [str(uuid4()) for _ in range(3)]
        mock_memory_service.bulk_memorize = AsyncMock(
            return_value=[MemoryOpResult(status="ok", data=mid, message="Stored") for mid in memory_ids]
        )

        response = client.post(
            "/v1/memory/bulk",
            headers=auth_headers,
            json={"memories": [{"content": f"Memory {i}", "tags": ["bulk"]} for i in range(3)]},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["stored_ids"]) == 3

    def test_memory_stats(self, client, auth_headers, mock_memory_service):
        """Test getting memory statistics."""
        mock_stats = {
            "total_memories": 1234,
            "memories_by_type": {"observation": 500, "task": 300, "concept": 234, "user": 200},
            "storage_size_mb": 45.6,
            "oldest_memory": "2024-01-01T00:00:00Z",
            "newest_memory": datetime.now(timezone.utc).isoformat(),
        }
        mock_memory_service.get_stats = AsyncMock(return_value=mock_stats)

        response = client.get("/v1/memory/stats", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total_memories"] == 1234
        assert data["data"]["memories_by_type"]["observation"] == 500

    def test_memory_export(self, client, auth_headers, mock_memory_service):
        """Test exporting memories."""
        mock_export_data = {
            "format": "json",
            "memories": [{"id": str(uuid4()), "content": "Memory 1"}, {"id": str(uuid4()), "content": "Memory 2"}],
            "metadata": {"export_date": datetime.now(timezone.utc).isoformat(), "total_count": 2},
        }
        mock_memory_service.export_memories = AsyncMock(return_value=mock_export_data)

        response = client.post(
            "/v1/memory/export",
            headers=auth_headers,
            json={"format": "json", "filters": {"tags": ["important"]}, "include_metadata": True},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["memories"]) == 2
        assert "export_date" in data["data"]["metadata"]

    def test_memory_import(self, client, auth_headers, mock_memory_service):
        """Test importing memories."""
        mock_memory_service.import_memories = AsyncMock(return_value={"imported": 5, "failed": 0, "skipped": 1})

        response = client.post(
            "/v1/memory/import",
            headers=auth_headers,
            json={
                "format": "json",
                "memories": [{"content": f"Imported memory {i}", "tags": ["import"]} for i in range(6)],
                "merge_strategy": "skip_duplicates",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["imported"] == 5
        assert data["data"]["skipped"] == 1
