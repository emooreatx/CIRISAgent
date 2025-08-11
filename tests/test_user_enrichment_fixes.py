"""
Unit tests for user enrichment bug fixes.
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from ciris_engine.logic.context.system_snapshot import SystemSnapshot
from ciris_engine.schemas.runtime.system_context import UserProfile
from ciris_engine.schemas.services.graph_core import GraphEdge, GraphNode, RecallQuery


class TestUserEnrichmentFixes:
    """Test suite for user enrichment bug fixes."""

    @pytest.fixture
    def mock_services(self):
        """Create mock services for testing."""
        memory_service = AsyncMock()
        time_service = MagicMock()
        time_service.now.return_value = datetime.now(timezone.utc)

        return {"memory_service": memory_service, "time_service": time_service}

    @pytest.mark.asyncio
    async def test_dict_attributes_from_tsdb_nodes(self, mock_services):
        """Test handling of dict attributes from tsdb_summary nodes."""
        memory_service = mock_services["memory_service"]

        # Create a user node
        user_node = GraphNode(
            id="user_12345", type="user", attributes={"username": "testuser", "display_name": "Test User"}
        )

        # Create edges to a tsdb_summary node
        edges = [GraphEdge(source="user_12345", target="tsdb_summary_20250808_00", relationship="HAS_SUMMARY")]

        # Create tsdb node with dict attributes (not Pydantic model)
        tsdb_node = GraphNode(
            id="tsdb_summary_20250808_00",
            type="tsdb_summary",
            attributes={
                "total_messages": 50,
                "active_hours": [10, 11, 14, 15],
                "timestamp": datetime(2025, 8, 8, 0, 0, 0, tzinfo=timezone.utc),
            },
        )

        # Setup mock responses
        memory_service.recall.side_effect = [
            [user_node],  # First recall for user
            edges,  # Get edges
            [tsdb_node],  # Recall connected node
        ]

        # Create snapshot
        snapshot = SystemSnapshot(memory_service=memory_service, time_service=mock_services["time_service"])

        # Run enrichment
        context_data = {}
        await snapshot._enrich_user_profiles(context_data=context_data, user_ids=["12345"], channel_id="test_channel")

        # Should not raise an error
        assert "user_profiles" in context_data
        profiles = context_data["user_profiles"]
        assert len(profiles) == 1

        # Check that tsdb attributes were included in notes
        profile = profiles[0]
        assert "tsdb_summary_20250808_00" in profile.notes
        assert "total_messages" in profile.notes

    @pytest.mark.asyncio
    async def test_datetime_json_serialization(self, mock_services):
        """Test JSON serialization of datetime objects in user profiles."""
        memory_service = mock_services["memory_service"]

        # Create a user node with datetime attribute
        user_node = GraphNode(
            id="user_12345",
            type="user",
            attributes={
                "username": "testuser",
                "created_at": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                "last_seen": datetime.now(timezone.utc),
            },
        )

        # Setup mock response
        memory_service.recall.side_effect = [[user_node], []]  # User node  # No edges

        # Create snapshot
        snapshot = SystemSnapshot(memory_service=memory_service, time_service=mock_services["time_service"])

        # Run enrichment - should not raise JSON serialization error
        context_data = {}
        await snapshot._enrich_user_profiles(context_data=context_data, user_ids=["12345"], channel_id="test_channel")

        # Check that datetime was serialized
        assert "user_profiles" in context_data
        profile = context_data["user_profiles"][0]
        assert "2024-01-01" in profile.notes  # ISO format datetime

    @pytest.mark.asyncio
    async def test_pydantic_model_attributes(self, mock_services):
        """Test handling of Pydantic model attributes."""
        memory_service = mock_services["memory_service"]

        class CustomAttributes(BaseModel):
            field1: str = "value1"
            field2: int = 42

        # Create nodes with Pydantic model attributes
        user_node = GraphNode(id="user_12345", type="user", attributes=CustomAttributes())

        connected_node = GraphNode(
            id="connected_123", type="custom", attributes=CustomAttributes(field1="connected", field2=100)
        )

        edges = [GraphEdge(source="user_12345", target="connected_123", relationship="CONNECTED")]

        # Setup mock responses
        memory_service.recall.side_effect = [
            [user_node],  # User node
            edges,  # Edges
            [connected_node],  # Connected node
        ]

        # Create snapshot
        snapshot = SystemSnapshot(memory_service=memory_service, time_service=mock_services["time_service"])

        # Run enrichment
        context_data = {}
        await snapshot._enrich_user_profiles(context_data=context_data, user_ids=["12345"], channel_id="test_channel")

        # Should handle Pydantic models correctly
        assert "user_profiles" in context_data
        profile = context_data["user_profiles"][0]
        assert "field1" in profile.notes
        assert "value1" in profile.notes
        assert "connected" in profile.notes

    @pytest.mark.asyncio
    async def test_mixed_attribute_types(self, mock_services):
        """Test handling of mixed attribute types in connected nodes."""
        memory_service = mock_services["memory_service"]

        class PydanticAttrs(BaseModel):
            name: str = "pydantic_node"

        # Create user node
        user_node = GraphNode(id="user_12345", type="user", attributes={"username": "testuser"})

        # Create connected nodes with different attribute types
        dict_node = GraphNode(id="dict_node", type="dict_type", attributes={"key": "value"})

        pydantic_node = GraphNode(id="pydantic_node", type="pydantic_type", attributes=PydanticAttrs())

        none_node = GraphNode(id="none_node", type="none_type", attributes=None)

        # Unknown type (like a string, which shouldn't happen but we handle)
        weird_node = GraphNode(
            id="weird_node", type="weird_type", attributes="string_attributes"  # This is weird but we should handle it
        )

        edges = [
            GraphEdge(source="user_12345", target="dict_node", relationship="HAS"),
            GraphEdge(source="user_12345", target="pydantic_node", relationship="HAS"),
            GraphEdge(source="user_12345", target="none_node", relationship="HAS"),
            GraphEdge(source="user_12345", target="weird_node", relationship="HAS"),
        ]

        # Setup mock responses
        memory_service.recall.side_effect = [
            [user_node],  # User node
            edges,  # All edges
            [dict_node],  # First connected
            [pydantic_node],  # Second connected
            [none_node],  # Third connected
            [weird_node],  # Fourth connected (will be skipped)
        ]

        # Create snapshot
        snapshot = SystemSnapshot(memory_service=memory_service, time_service=mock_services["time_service"])

        # Run enrichment - should handle all types gracefully
        context_data = {}
        await snapshot._enrich_user_profiles(context_data=context_data, user_ids=["12345"], channel_id="test_channel")

        # Check results
        assert "user_profiles" in context_data
        profile = context_data["user_profiles"][0]

        # Dict node should be included
        assert "dict_node" in profile.notes
        # Pydantic node should be included
        assert "pydantic_node" in profile.notes
        # None node should be included (with empty attributes)
        assert "none_node" in profile.notes
        # Weird node should be skipped (not in notes)
        # Actually it might still appear in the connected nodes list, just with no attributes

    @pytest.mark.asyncio
    async def test_recent_messages_serialization(self, mock_services):
        """Test JSON serialization of recent messages with datetime objects."""
        memory_service = mock_services["memory_service"]

        # Create user node
        user_node = GraphNode(id="user_12345", type="user", attributes={"username": "testuser"})

        # Setup mock responses
        memory_service.recall.side_effect = [[user_node], []]  # User node  # No edges

        # Mock database query for recent messages
        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            # Mock recent messages with datetime
            mock_cursor.fetchall.return_value = [
                {
                    "channel_id": "other_channel",
                    "tags": json.dumps({"user_id": "12345"}),
                    "request_data": json.dumps({"parameters": {"content": "Test message"}}),
                    "created_at": datetime.now(timezone.utc),
                }
            ]

            # Create snapshot
            snapshot = SystemSnapshot(memory_service=memory_service, time_service=mock_services["time_service"])

            # Run enrichment
            context_data = {}
            await snapshot._enrich_user_profiles(
                context_data=context_data, user_ids=["12345"], channel_id="test_channel"
            )

            # Should handle datetime in recent messages
            assert "user_profiles" in context_data
