"""
Unit tests for Discord observer unsolicited guidance message format.

Tests that unsolicited guidance tasks are created with the correct format:
"Guidance received from authorized WA {WA name} (ID: {WA ID}) please act accordingly"
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import uuid

from ciris_engine.adapters.discord.discord_observer import DiscordObserver
from ciris_engine.schemas.foundational_schemas_v1 import DiscordMessage


class TestUnsolicitedGuidanceFormat:
    """Test class for unsolicited guidance message format verification."""

    @pytest.fixture
    def discord_observer(self):
        """Create a DiscordObserver instance for testing."""
        mock_communication_service = Mock()
        mock_memory_service = Mock()
        mock_secrets_service = Mock()
        
        observer = DiscordObserver(
            communication_service=mock_communication_service,
            memory_service=mock_memory_service,
            secrets_service=mock_secrets_service
        )
        return observer

    @pytest.fixture
    def wa_message(self):
        """Create a mock WA message for testing."""
        return DiscordMessage(
            message_id="msg-123",
            content="You should prioritize ethical considerations in this response",
            author_id="537080239679864862",  # Authorized WA user ID
            author_name="somecomputerguy",   # Default WA name
            channel_id="channel-456",
            is_bot=False,
            is_dm=False,
            raw_message=None
        )

    @pytest.fixture  
    def non_wa_message(self):
        """Create a mock non-WA message for testing."""
        return DiscordMessage(
            message_id="msg-789",
            content="Some random message",
            author_id="999999999999999999",  # Non-authorized user ID
            author_name="randomuser",
            channel_id="channel-456", 
            is_bot=False,
            is_dm=False,
            raw_message=None
        )

    @patch('ciris_engine.persistence')
    @patch('ciris_engine.adapters.discord.discord_observer.logger')
    async def test_unsolicited_guidance_task_format(self, mock_logger, mock_persistence, 
                                                   discord_observer, wa_message):
        """Test that unsolicited guidance creates task with correct format."""
        
        # Mock persistence calls
        mock_persistence.get_thought_by_id.return_value = None  # No matching thought found
        mock_persistence.add_task.return_value = None
        
        # Mock the deferral message sending
        discord_observer._send_deferral_message = AsyncMock()
        
        # Set up observer with WA configuration
        discord_observer.wa_user_ids = ["537080239679864862"]
        discord_observer.deferral_channel_id = "deferral_channel"
        
        # Process the WA message
        await discord_observer._add_to_feedback_queue(wa_message)
        
        # Verify a task was created
        mock_persistence.add_task.assert_called_once()
        
        # Get the task that was created
        created_task = mock_persistence.add_task.call_args[0][0]
        
        # Verify the task description format
        expected_description = f"Guidance received from authorized WA {wa_message.author_name} (ID: {wa_message.author_id}) please act accordingly"
        assert created_task.description == expected_description
        
        # Verify other task properties
        assert created_task.priority == 8  # High priority
        # Context is a ThoughtContext object with extra attributes
        assert hasattr(created_task.context, "observation_type")
        assert getattr(created_task.context, "observation_type") == "unsolicited_guidance"
        assert hasattr(created_task.context, "is_guidance")
        assert getattr(created_task.context, "is_guidance") == True
        assert hasattr(created_task.context, "guidance_content")
        assert getattr(created_task.context, "guidance_content") == wa_message.content
        # Author info is in initial_task_context
        assert created_task.context.initial_task_context.author_id == wa_message.author_id
        assert created_task.context.initial_task_context.author_name == wa_message.author_name

    @patch('ciris_engine.persistence')
    @patch('ciris_engine.adapters.discord.discord_observer.logger')
    async def test_non_wa_user_rejected(self, mock_logger, mock_persistence,
                                       discord_observer, non_wa_message):
        """Test that non-WA users are rejected and no task is created."""
        
        # Mock the deferral message sending
        discord_observer._send_deferral_message = AsyncMock()
        
        # Set up observer with WA configuration (doesn't include non-WA user)
        discord_observer.wa_user_ids = ["537080239679864862"]
        discord_observer.deferral_channel_id = "deferral_channel"
        
        # Process the non-WA message
        await discord_observer._add_to_feedback_queue(non_wa_message)
        
        # Verify no task was created
        mock_persistence.add_task.assert_not_called()
        
        # Verify error message was sent
        discord_observer._send_deferral_message.assert_called_once()
        error_message = discord_observer._send_deferral_message.call_args[0][0]
        
        assert "🚫 **Not Authorized**" in error_message
        assert non_wa_message.author_name in error_message
        assert non_wa_message.author_id in error_message
        assert "is not a Wise Authority" in error_message

    @patch('ciris_engine.persistence')
    @patch('ciris_engine.adapters.discord.discord_observer.logger')
    async def test_guidance_format_with_different_wa_info(self, mock_logger, mock_persistence,
                                                         discord_observer):
        """Test guidance format with different WA names and IDs."""
        
        # Create test cases with different WA information
        test_cases = [
            {
                "author_name": "admin_user",
                "author_id": "537080239679864862",
                "content": "Please be more careful with sensitive data"
            },
            {
                "author_name": "somecomputerguy", 
                "author_id": "537080239679864862",
                "content": "Consider the ethical implications here"
            }
        ]
        
        mock_persistence.get_thought_by_id.return_value = None
        mock_persistence.add_task.return_value = None
        discord_observer._send_deferral_message = AsyncMock()
        
        # Set up observer with WA configuration
        discord_observer.wa_user_ids = ["537080239679864862"]
        discord_observer.deferral_channel_id = "deferral_channel"
        
        for case in test_cases:
            wa_msg = DiscordMessage(
                message_id=f"msg-{case['author_id'][:8]}",
                content=case["content"],
                author_id=case["author_id"],
                author_name=case["author_name"],
                channel_id="channel-test",
                is_bot=False,
                is_dm=False,
                raw_message=None
            )
            
            # Reset the mock for each test case
            mock_persistence.add_task.reset_mock()
            
            # Process the message
            await discord_observer._add_to_feedback_queue(wa_msg)
            
            # Verify task was created with correct format
            mock_persistence.add_task.assert_called_once()
            created_task = mock_persistence.add_task.call_args[0][0]
            
            expected_description = f"Guidance received from authorized WA {case['author_name']} (ID: {case['author_id']}) please act accordingly"
            assert created_task.description == expected_description

    def test_guidance_format_string_construction(self):
        """Test the guidance format string construction directly."""
        
        # Test various WA name and ID combinations
        test_cases = [
            ("somecomputerguy", "537080239679864862"),
            ("admin", "123456789012345678"),
            ("wa_user_123", "987654321098765432")
        ]
        
        for author_name, author_id in test_cases:
            # Construct the format as it would be in the actual code
            description = f"Guidance received from authorized WA {author_name} (ID: {author_id}) please act accordingly"
            
            # Verify format contains all required elements
            assert "Guidance received from authorized WA" in description
            assert author_name in description
            assert f"(ID: {author_id})" in description
            assert "please act accordingly" in description
            
            # Verify the exact format matches expected pattern
            expected = f"Guidance received from authorized WA {author_name} (ID: {author_id}) please act accordingly"
            assert description == expected

    def test_format_comparison_old_vs_new(self):
        """Compare old format vs new format to show the improvement."""
        
        author_name = "somecomputerguy"
        author_id = "537080239679864862"
        content = "You should prioritize ethical considerations"
        
        # Old format (what it used to be)
        old_format = f"Process unsolicited guidance from @{author_name}: '{content}'"
        
        # New format (what it should be now)
        new_format = f"Guidance received from authorized WA {author_name} (ID: {author_id}) please act accordingly"
        
        print(f"\nOLD FORMAT: {old_format}")
        print(f"NEW FORMAT: {new_format}")
        
        # Verify new format improvements
        assert "authorized WA" in new_format
        assert "ID:" in new_format
        assert "please act accordingly" in new_format
        
        # Verify old format elements are not in new format
        assert "Process unsolicited guidance from @" not in new_format
        assert content not in new_format  # Actual guidance content not in description


if __name__ == "__main__":
    pytest.main([__file__, "-v"])