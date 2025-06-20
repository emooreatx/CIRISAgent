#!/usr/bin/env python3
"""
Pytest unit tests for observe handler _recall_from_messages logic.

Tests the message unpacking and memory recall logic from the observer in the platform adapter.
"""
import pytest
import asyncio
import logging
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, AsyncMock
import sys
import os

# Add the project root to sys.path to import modules
sys.path.insert(0, '/home/emoore/CIRISAgent')

from ciris_engine.schemas.graph_schemas_v1 import GraphScope, GraphNode, NodeType
from ciris_engine.action_handlers.observe_handler import ObserveHandler
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies
from ciris_engine.message_buses.bus_manager import BusManager

# Configure logging for tests
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class MockMemoryService:
    """Mock memory service to track recall calls"""
    def __init__(self):
        self.recall_calls = []
        self.recall_errors = {}  # Dict to simulate recall failures for specific node_id/scope combinations
    
    async def recall(self, recall_query, handler_name: str = None):
        """Mock recall method that logs calls and can simulate failures"""
        # Handle both MemoryQuery and direct parameters
        if hasattr(recall_query, 'node_id') and hasattr(recall_query, 'scope'):
            node_id = recall_query.node_id
            scope = recall_query.scope
        else:
            # Fallback for any other format
            node_id = getattr(recall_query, 'id', str(recall_query))
            scope = getattr(recall_query, 'scope', None)
            
        self.recall_calls.append((node_id, scope))
        
        # Check if we should simulate an error for this call
        error_key = (node_id, scope)
        if error_key in self.recall_errors:
            raise self.recall_errors[error_key]
        
        # Return empty list as expected by the protocol
        return []
    
    def set_recall_error(self, node_id: str, scope: GraphScope, error: Exception):
        """Set an error to be raised for a specific recall call"""
        self.recall_errors[(node_id, scope)] = error
    
    def clear_errors(self):
        """Clear all recall errors"""
        self.recall_errors.clear()


@pytest.fixture
def mock_memory_service():
    """Fixture providing a fresh MockMemoryService instance"""
    return MockMemoryService()


@pytest.fixture
def observe_handler(mock_memory_service):
    """Fixture providing an ObserveHandler instance with minimal dependencies"""
    from unittest.mock import AsyncMock
    
    # Create minimal dependencies with a mocked secrets service
    service_registry = AsyncMock()
    
    # Mock the secrets service to avoid abstract class instantiation issues
    mock_secrets_service = AsyncMock()
    mock_secrets_service.process_incoming_text = AsyncMock(return_value=("test", []))
    mock_secrets_service.decapsulate_secrets = AsyncMock(side_effect=lambda x, **kwargs: x)
    mock_secrets_service.get_secret_references = AsyncMock(return_value=[])
    mock_secrets_service.recall_secret = AsyncMock(return_value={})
    mock_secrets_service.update_secrets_filter = AsyncMock(return_value={})
    mock_secrets_service.rotate_encryption_keys = AsyncMock(return_value=True)
    
    bus_manager = BusManager(service_registry)
    
    # Mock the memory bus to use our mock_memory_service
    mock_memory_bus = AsyncMock()
    mock_memory_bus.recall = mock_memory_service.recall
    bus_manager.memory = mock_memory_bus
    
    deps = ActionHandlerDependencies(
        bus_manager=bus_manager,
        secrets_service=mock_secrets_service
    )
    return ObserveHandler(deps)


@pytest.fixture
def sample_messages():
    """Fixture providing sample messages that match Discord adapter structure"""
    from ciris_engine.schemas.foundational_schemas_v1 import FetchedMessage

    return [
        FetchedMessage(
            id="1234567890123456789",
            content="Hello, this is a test message",
            author_id="987654321098765432",
            author_name="TestUser1",
            timestamp="2025-06-01T19:36:02.661000",
            is_bot=False,
        ),
        FetchedMessage(
            id="1234567890123456790",
            content="Another test message",
            author_id="987654321098765433",
            author_name="TestUser2",
            timestamp="2025-06-01T19:36:03.661000",
            is_bot=False,
        ),
        FetchedMessage(
            id="1234567890123456791",
            content="Bot message should be recalled too",
            author_id="987654321098765434",
            author_name="TestBot",
            timestamp="2025-06-01T19:36:04.661000",
            is_bot=True,
        ),
        FetchedMessage(
            id="1234567890123456792",
            content="Message with no author_id",
            author_name="SystemMessage",
            timestamp="2025-06-01T19:36:05.661000",
            is_bot=False,
        ),
    ]


@pytest.fixture
def malformed_messages():
    """Fixture providing malformed messages to test edge cases"""
    from ciris_engine.schemas.foundational_schemas_v1 import FetchedMessage

    return [
        FetchedMessage(),  # Empty message
        FetchedMessage(content="Message with only content"),
        FetchedMessage(author_id="", content="Empty author_id"),
        FetchedMessage(author_id=None, content="None author_id"),
    ]


@pytest.fixture
def duplicate_author_messages():
    """Fixture providing messages with duplicate author IDs"""
    from ciris_engine.schemas.foundational_schemas_v1 import FetchedMessage

    return [
        FetchedMessage(
            id="msg1",
            content="First message",
            author_id="user123",
            author_name="TestUser",
            timestamp="2025-06-01T19:36:02.661000",
            is_bot=False,
        ),
        FetchedMessage(
            id="msg2",
            content="Second message from same user",
            author_id="user123",
            author_name="TestUser",
            timestamp="2025-06-01T19:36:03.661000",
            is_bot=False,
        ),
        FetchedMessage(
            id="msg3",
            content="Third message from same user",
            author_id="user123",
            author_name="TestUser",
            timestamp="2025-06-01T19:36:04.661000",
            is_bot=False,
        ),
    ]


class TestObserveHandlerRecallLogic:
    """Test class for observe handler _recall_from_messages logic"""

    @pytest.mark.asyncio
    async def test_normal_message_processing(self, observe_handler, mock_memory_service, sample_messages):
        """Test normal message processing with valid messages"""
        channel_id = "123456789012345678"
        
        await observe_handler._recall_from_messages(channel_id, sample_messages)
        
        # Analyze results
        recall_by_node = {}
        for node_id, scope in mock_memory_service.recall_calls:
            if node_id not in recall_by_node:
                recall_by_node[node_id] = []
            recall_by_node[node_id].append(scope)
        
        # Expected: 1 channel + 3 users (message 4 has no author_id) = 4 nodes × 3 scopes = 12 calls
        expected_nodes = 4  # channel + 3 valid author_ids
        expected_calls = expected_nodes * 3  # 3 scopes each
        
        assert len(recall_by_node) == expected_nodes
        assert len(mock_memory_service.recall_calls) == expected_calls
        
        # Verify specific node recalls
        assert f"channel/{channel_id}" in recall_by_node
        assert "user/987654321098765432" in recall_by_node
        assert "user/987654321098765433" in recall_by_node
        assert "user/987654321098765434" in recall_by_node
        
        # Verify each node has all 3 scopes
        for node_id, scopes in recall_by_node.items():
            assert len(scopes) == 3
            assert GraphScope.IDENTITY in scopes
            assert GraphScope.ENVIRONMENT in scopes
            assert GraphScope.LOCAL in scopes

    @pytest.mark.asyncio
    async def test_no_memory_service(self, observe_handler, sample_messages):
        """Test handling when no memory service is provided"""
        channel_id = "test_channel"
        
        # Should not raise an exception and should return gracefully
        await observe_handler._recall_from_messages(channel_id, sample_messages)

    @pytest.mark.asyncio
    async def test_no_channel_id(self, observe_handler, mock_memory_service, sample_messages):
        """Test handling when no channel_id is provided"""
        await observe_handler._recall_from_messages(None, sample_messages)
        
        # Should only have user recalls, no channel recall
        recall_by_node = {}
        for node_id, scope in mock_memory_service.recall_calls:
            if node_id not in recall_by_node:
                recall_by_node[node_id] = []
            recall_by_node[node_id].append(scope)
        
        channel_nodes = [node for node in recall_by_node.keys() if node.startswith("channel/")]
        assert len(channel_nodes) == 0
        
        # Should have 3 user nodes (message 4 has no author_id)
        user_nodes = [node for node in recall_by_node.keys() if node.startswith("user/")]
        assert len(user_nodes) == 3

    @pytest.mark.asyncio
    async def test_empty_messages(self, observe_handler, mock_memory_service):
        """Test handling when messages list is empty"""
        channel_id = "test_channel"
        
        await observe_handler._recall_from_messages(channel_id, [])
        
        # Should only have channel recall
        recall_by_node = {}
        for node_id, scope in mock_memory_service.recall_calls:
            if node_id not in recall_by_node:
                recall_by_node[node_id] = []
            recall_by_node[node_id].append(scope)
        
        assert len(recall_by_node) == 1
        assert f"channel/{channel_id}" in recall_by_node
        assert len(recall_by_node[f"channel/{channel_id}"]) == 3  # All 3 scopes

    @pytest.mark.asyncio
    async def test_none_messages(self, observe_handler, mock_memory_service):
        """Test handling when messages is None"""
        channel_id = "test_channel"
        
        await observe_handler._recall_from_messages(channel_id, None)
        
        # Should only have channel recall
        recall_by_node = {}
        for node_id, scope in mock_memory_service.recall_calls:
            if node_id not in recall_by_node:
                recall_by_node[node_id] = []
            recall_by_node[node_id].append(scope)
        
        assert len(recall_by_node) == 1
        assert f"channel/{channel_id}" in recall_by_node

    @pytest.mark.asyncio
    async def test_malformed_messages(self, observe_handler, mock_memory_service, malformed_messages):
        """Test handling of malformed messages"""
        channel_id = "test_channel"
        
        await observe_handler._recall_from_messages(channel_id, malformed_messages)
        
        # Should only have channel recall (no valid author_ids in malformed messages)
        recall_by_node = {}
        for node_id, scope in mock_memory_service.recall_calls:
            if node_id not in recall_by_node:
                recall_by_node[node_id] = []
            recall_by_node[node_id].append(scope)
        
        # Should only have channel recall
        assert len(recall_by_node) == 1
        assert f"channel/{channel_id}" in recall_by_node
        
        # No valid user recalls should be present
        user_nodes = [node for node in recall_by_node.keys() if node.startswith("user/") and len(node) > 5]
        assert len(user_nodes) == 0

    @pytest.mark.asyncio
    async def test_duplicate_author_handling(self, observe_handler, mock_memory_service, duplicate_author_messages):
        """Test handling of duplicate author IDs"""
        channel_id = "test_channel"
        
        await observe_handler._recall_from_messages(channel_id, duplicate_author_messages)
        
        # Analyze results - should only recall each unique ID once per scope
        recall_by_node = {}
        for node_id, scope in mock_memory_service.recall_calls:
            if node_id not in recall_by_node:
                recall_by_node[node_id] = []
            recall_by_node[node_id].append(scope)
        
        # Should have channel + 1 unique user = 2 nodes
        assert len(recall_by_node) == 2
        assert f"channel/{channel_id}" in recall_by_node
        assert "user/user123" in recall_by_node
        
        # Each node should have exactly 3 scope recalls
        for node_id, scopes in recall_by_node.items():
            assert len(scopes) == 3

    @pytest.mark.asyncio
    async def test_recall_error_handling(self, observe_handler, mock_memory_service):
        """Test handling of recall errors"""
        channel_id = "test_channel"
        from ciris_engine.schemas.foundational_schemas_v1 import FetchedMessage
        messages = [
            FetchedMessage(
                id="test_msg",
                content="Test message",
                author_id="test_user",
                author_name="TestUser",
                timestamp="2025-06-01T19:36:02.661000",
                is_bot=False,
            )
        ]
        
        # Set up some recall errors
        mock_memory_service.set_recall_error("user/test_user", GraphScope.IDENTITY, RuntimeError("Test error"))
        mock_memory_service.set_recall_error(f"channel/{channel_id}", GraphScope.ENVIRONMENT, ValueError("Another test error"))
        
        # Should not raise an exception despite recall errors
        await observe_handler._recall_from_messages(channel_id, messages)
        
        # Should still attempt all recalls
        assert len(mock_memory_service.recall_calls) == 6  # 2 nodes × 3 scopes each

    @pytest.mark.asyncio
    async def test_message_structure_validation(self, sample_messages):
        """Test that sample messages have the expected structure"""
        required_fields = ["id", "content", "author_name", "timestamp", "is_bot"]

        for i, msg in enumerate(sample_messages):
            data = msg.model_dump(by_alias=True)
            for field in required_fields:
                assert field in data, f"Message {i+1} missing required field '{field}'"

            # Most messages should have author_id (except test message 4)
            if i < 3:
                assert data.get("author_id")

            assert isinstance(data.get("content"), str)
            assert isinstance(data.get("is_bot"), bool)

    @pytest.mark.asyncio
    async def test_id_format_consistency(self, observe_handler, mock_memory_service):
        """Test that recall IDs follow consistent format"""
        channel_id = "123456789"
        from ciris_engine.schemas.foundational_schemas_v1 import FetchedMessage
        messages = [
            FetchedMessage(
                id="msg1",
                content="Test",
                author_id="user456",
                author_name="Test",
                timestamp="2025-06-01T19:36:02.661000",
                is_bot=False,
            )
        ]
        
        await observe_handler._recall_from_messages(channel_id, messages)
        
        # Check that all recall calls use correct ID format
        for node_id, scope in mock_memory_service.recall_calls:
            if node_id.startswith("channel/"):
                assert node_id == f"channel/{channel_id}"
            elif node_id.startswith("user/"):
                assert node_id == "user/user456"
            else:
                pytest.fail(f"Unexpected node_id format: {node_id}")

    @pytest.mark.asyncio
    async def test_scope_coverage(self, observe_handler, mock_memory_service):
        """Test that all GraphScope values are used in recalls"""
        channel_id = "test_channel"
        from ciris_engine.schemas.foundational_schemas_v1 import FetchedMessage
        messages = [
            FetchedMessage(
                id="msg1",
                content="Test",
                author_id="test_user",
                author_name="Test",
                timestamp="2025-06-01T19:36:02.661000",
                is_bot=False,
            )
        ]
        
        await observe_handler._recall_from_messages(channel_id, messages)
        
        # Collect all scopes used
        scopes_used = set()
        for node_id, scope in mock_memory_service.recall_calls:
            scopes_used.add(scope)
        
        # Should use all 3 scopes
        expected_scopes = {GraphScope.IDENTITY, GraphScope.ENVIRONMENT, GraphScope.LOCAL}
        assert scopes_used == expected_scopes

    @pytest.mark.parametrize("channel_id,expected_channel_recalls", [
        ("123", 3),  # Normal channel ID
        ("", 0),     # Empty channel ID should not create recalls  
        (None, 0),   # None channel ID should not create recalls
    ])
    @pytest.mark.asyncio
    async def test_channel_id_variations(self, observe_handler, mock_memory_service, channel_id, expected_channel_recalls):
        """Test various channel_id values"""
        from ciris_engine.schemas.foundational_schemas_v1 import FetchedMessage
        messages = [
            FetchedMessage(
                id="msg1",
                content="Test",
                author_id="test_user",
                author_name="Test",
                timestamp="2025-06-01T19:36:02.661000",
                is_bot=False,
            )
        ]
        
        await observe_handler._recall_from_messages(channel_id, messages)
        
        # Count channel recalls
        channel_recalls = [call for call in mock_memory_service.recall_calls if call[0].startswith("channel/")]
        assert len(channel_recalls) == expected_channel_recalls

    @pytest.mark.parametrize("author_id,should_recall", [
        ("valid_user_123", True),
        ("", False),  # Empty string should not create recall
        (None, False),  # None should not create recall
        ("0", True),  # "0" is a valid string
        ("user with spaces", True),  # Spaces should be fine
    ])
    @pytest.mark.asyncio
    async def test_author_id_variations(self, observe_handler, mock_memory_service, author_id, should_recall):
        """Test various author_id values"""
        from ciris_engine.schemas.foundational_schemas_v1 import FetchedMessage
        message = FetchedMessage(
            id="msg1",
            content="Test",
            author_name="Test",
            timestamp="2025-06-01T19:36:02.661000",
            is_bot=False,
        )

        if author_id is not None:
            message.author_id = author_id

        await observe_handler._recall_from_messages("test_channel", [message])
        
        # Count user recalls
        user_recalls = [call for call in mock_memory_service.recall_calls if call[0].startswith("user/")]
        
        if should_recall:
            assert len(user_recalls) == 3  # 3 scopes
            assert all(call[0] == f"user/{author_id}" for call in user_recalls)
        else:
            assert len(user_recalls) == 0
