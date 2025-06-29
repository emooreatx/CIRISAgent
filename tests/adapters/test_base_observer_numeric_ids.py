"""
Unit tests for base observer numeric ID handling.
Tests that the observer properly includes numeric IDs in task descriptions and thought content.
"""
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import uuid

from ciris_engine.logic.adapters.base_observer import BaseObserver
from ciris_engine.schemas.runtime.messages import DiscordMessage
from ciris_engine.schemas.runtime.models import Task, Thought, TaskContext
from ciris_engine.schemas.runtime.enums import TaskStatus, ThoughtStatus, ThoughtType
from ciris_engine.logic.services.lifecycle.time import TimeService
from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphScope


class ConcreteObserver(BaseObserver[DiscordMessage]):
    """Concrete implementation for testing."""

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass


class TestBaseObserverNumericIds:
    """Test base observer properly handles numeric IDs."""

    @pytest.fixture
    def time_service(self):
        """Create a time service."""
        return TimeService()

    @pytest.fixture
    def mock_memory_service(self):
        """Create mock memory service."""
        memory = AsyncMock()
        memory.recall = AsyncMock(return_value=[])
        return memory

    @pytest.fixture
    def mock_bus_manager(self):
        """Create mock bus manager."""
        bus_manager = Mock()
        bus_manager.communication = AsyncMock()
        return bus_manager

    @pytest.fixture
    def observer(self, time_service, mock_memory_service, mock_bus_manager):
        """Create observer instance."""
        return ConcreteObserver(
            on_observe=AsyncMock(),
            bus_manager=mock_bus_manager,
            memory_service=mock_memory_service,
            time_service=time_service,
            origin_service="test"
        )

    @pytest.mark.asyncio
    async def test_passive_observation_includes_numeric_id(self, observer, time_service):
        """Test that passive observations include numeric user IDs in descriptions."""
        # Create a test message with numeric ID
        test_msg = DiscordMessage(
            message_id="msg123",
            author_id="537080239679864862",  # Numeric Discord ID
            author_name="SomeComputerGuy",
            content="Hello, do you remember me?",
            channel_id="1234567890",
            is_bot=False
        )

        # Mock persistence to capture the task
        captured_task = None
        captured_thought = None

        def capture_task(task):
            nonlocal captured_task
            captured_task = task

        def capture_thought(thought):
            nonlocal captured_thought
            captured_thought = thought

        # Patch persistence
        with patch('ciris_engine.logic.persistence.add_task', side_effect=capture_task):
            with patch('ciris_engine.logic.persistence.add_thought', side_effect=capture_thought):
                await observer._create_passive_observation_result(test_msg)

        # Verify task was created with numeric ID in description
        assert captured_task is not None
        assert "SomeComputerGuy (ID: 537080239679864862)" in captured_task.description
        assert captured_task.context.user_id == "537080239679864862"

        # Verify thought content includes numeric ID
        assert captured_thought is not None
        assert "SomeComputerGuy (ID: 537080239679864862)" in captured_thought.content

    @pytest.mark.asyncio
    async def test_conversation_history_includes_numeric_ids(self, observer, time_service):
        """Test that conversation history includes numeric IDs for all messages."""
        # Add some messages to history
        observer._history = [
            DiscordMessage(
                message_id="msg1",
                author_id="111111111111111111",
                author_name="User1",
                content="First message",
                channel_id="1234567890",
                is_bot=False
            ),
            DiscordMessage(
                message_id="msg2",
                author_id="222222222222222222",
                author_name="User2",
                content="Second message",
                channel_id="1234567890",
                is_bot=False
            )
        ]

        # Current message
        current_msg = DiscordMessage(
            message_id="msg3",
            author_id="333333333333333333",
            author_name="User3",
            content="Current message",
            channel_id="1234567890",
            is_bot=False
        )

        captured_thought = None

        def capture_thought(thought):
            nonlocal captured_thought
            captured_thought = thought

        # Patch persistence
        with patch('ciris_engine.logic.persistence.add_task'):
            with patch('ciris_engine.logic.persistence.add_thought', side_effect=capture_thought):
                await observer._create_passive_observation_result(current_msg)

        # Verify all messages in history have numeric IDs
        assert captured_thought is not None
        thought_content = captured_thought.content

        # Check each user appears with their numeric ID
        assert "User1 (ID: 111111111111111111)" in thought_content
        assert "User2 (ID: 222222222222222222)" in thought_content
        assert "User3 (ID: 333333333333333333)" in thought_content

    @pytest.mark.asyncio
    async def test_priority_observation_includes_numeric_id(self, observer, time_service):
        """Test that priority observations include numeric user IDs."""
        test_msg = DiscordMessage(
            message_id="urgent123",
            author_id="999888777666555444",
            author_name="UrgentUser",
            content="URGENT: Please help immediately!",
            channel_id="1234567890",
            is_bot=False
        )

        # Mock filter result
        filter_result = Mock()
        filter_result.priority = Mock(value="high")
        filter_result.reasoning = "Urgent keyword detected"

        captured_task = None
        captured_thought = None

        def capture_task(task):
            nonlocal captured_task
            captured_task = task

        def capture_thought(thought):
            nonlocal captured_thought
            captured_thought = thought

        # Patch persistence
        with patch('ciris_engine.logic.persistence.add_task', side_effect=capture_task):
            with patch('ciris_engine.logic.persistence.add_thought', side_effect=capture_thought):
                await observer._create_priority_observation_result(test_msg, filter_result)

        # Verify priority task includes numeric ID
        assert captured_task is not None
        assert "UrgentUser (ID: 999888777666555444)" in captured_task.description
        assert captured_task.context.user_id == "999888777666555444"

        # Verify priority thought includes numeric ID
        assert captured_thought is not None
        assert "UrgentUser (ID: 999888777666555444)" in captured_thought.content

    @pytest.mark.skip(reason="Base observer _recall_context implementation needs update")
    @pytest.mark.asyncio
    async def test_recall_context_uses_numeric_ids(self, observer, mock_memory_service):
        """Test that _recall_context uses numeric user IDs for recall."""
        # Add messages with numeric IDs to history
        observer._history = [
            DiscordMessage(
                message_id="msg1",
                author_id="123456789012345678",
                author_name="TestUser",
                content="Test",
                channel_id="9876543210",
                is_bot=False
            )
        ]

        test_msg = DiscordMessage(
            message_id="msg2",
            author_id="987654321098765432",
            author_name="AnotherUser",
            content="Hello",
            channel_id="9876543210",
            is_bot=False
        )

        # Call _recall_context
        await observer._recall_context(test_msg)

        # Verify memory service was called
        assert mock_memory_service.recall.called

        # The _recall_context method in base_observer passes a GraphNode to recall
        # Check that numeric user IDs were used in the recall calls
        recall_calls = mock_memory_service.recall.call_args_list

        # Look for user node recalls
        user_node_found = False
        for call in recall_calls:
            # The recall method is called with a GraphNode argument
            if len(call[0]) > 0:
                node = call[0][0]
                if hasattr(node, 'id') and node.id == 'user/123456789012345678':
                    user_node_found = True
                    break

        # Should have tried to recall the user from history with numeric ID
        assert user_node_found, "Expected recall to be called with user/123456789012345678"
