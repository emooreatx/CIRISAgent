"""
Unit tests for Discord message handler.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone
import discord

from ciris_engine.logic.adapters.discord.discord_message_handler import DiscordMessageHandler
from ciris_engine.schemas.runtime.messages import IncomingMessage, FetchedMessage


class TestDiscordMessageHandler:
    """Test Discord message handling functionality."""

    @pytest.fixture
    def mock_bot(self):
        """Create a mock Discord bot."""
        bot = Mock()
        bot.user = Mock(id=12345, name="TestBot")
        bot.get_channel = Mock()
        bot.wait_until_ready = AsyncMock()
        bot.fetch_channel = AsyncMock()
        return bot

    @pytest.fixture
    def handler(self, mock_bot):
        """Create message handler instance."""
        return DiscordMessageHandler(mock_bot)

    @pytest.mark.asyncio
    async def test_send_message_success(self, handler, mock_bot):
        """Test successful message sending."""
        mock_channel = Mock()
        mock_channel.send = AsyncMock(return_value=Mock(id=123))
        mock_bot.get_channel.return_value = mock_channel
        
        # Mock the client as not closed for the new check
        mock_bot.is_closed.return_value = False

        # send_message_to_channel returns None on success, raises exception on failure
        await handler.send_message_to_channel("123456789", "Hello world")
        mock_channel.send.assert_called_once_with("Hello world")

    @pytest.mark.asyncio
    async def test_send_message_channel_not_found(self, handler, mock_bot):
        """Test sending message when channel not found."""
        mock_bot.get_channel.return_value = None
        mock_bot.fetch_channel = AsyncMock(side_effect=discord.NotFound(Mock(), "Channel not found"))
        
        # Mock the client as not closed for the new check
        mock_bot.is_closed.return_value = False

        with pytest.raises(RuntimeError, match="Discord channel.*not found"):
            await handler.send_message_to_channel("999999999", "Hello")

    @pytest.mark.asyncio
    async def test_send_message_with_error(self, handler, mock_bot):
        """Test handling send errors."""
        mock_channel = Mock()
        mock_channel.send = AsyncMock(side_effect=Exception("Send failed"))
        mock_bot.get_channel.return_value = mock_channel
        
        # Mock the client as not closed for the new check
        mock_bot.is_closed.return_value = False

        # send_message_to_channel propagates exceptions
        with pytest.raises(Exception, match="Send failed"):
            await handler.send_message_to_channel("123456789", "Hello")

    @pytest.mark.asyncio
    async def test_fetch_messages_success(self, handler, mock_bot):
        """Test fetching messages from channel."""
        # Create mock Discord messages
        mock_msg1 = Mock(
            id=1,
            content="First message",
            author=Mock(id=111, name="User1", display_name="User1", bot=False),
            created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            channel=Mock(id=123)
        )
        mock_msg2 = Mock(
            id=2,
            content="Second message",
            author=Mock(id=222, name="User2", display_name="User2", bot=False),
            created_at=datetime(2024, 1, 1, 10, 5, 0, tzinfo=timezone.utc),
            channel=Mock(id=123)
        )

        # Setup channel history - use async iterator
        mock_channel = Mock()

        # Create async iterator for channel.history
        async def mock_history(limit):
            for msg in [mock_msg1, mock_msg2]:
                yield msg

        mock_channel.history = mock_history

        # Mock _resolve_channel to return our mock channel
        with patch.object(handler, '_resolve_channel', return_value=mock_channel):
            messages = await handler.fetch_messages_from_channel("123456789012345678", 10)

        assert len(messages) == 2
        assert isinstance(messages[0], FetchedMessage)
        assert messages[0].content == "First message"
        assert messages[0].author_id == "111"
        assert messages[0].author_name == "User1"
        assert messages[1].content == "Second message"

    @pytest.mark.asyncio
    async def test_fetch_messages_empty_channel(self, handler, mock_bot):
        """Test fetching from empty channel."""
        mock_channel = Mock()

        # Create empty async iterator
        async def mock_history(limit):
            return
            yield  # Make it a generator

        mock_channel.history = mock_history

        with patch.object(handler, '_resolve_channel', return_value=mock_channel):
            messages = await handler.fetch_messages_from_channel("123456789012345678", 10)

        assert messages == []


    @pytest.mark.asyncio
    async def test_filter_bot_messages(self, handler, mock_bot):
        """Test that bot messages are filtered out."""
        # Create mix of user and bot messages
        user_msg = Mock(
            id=1,
            content="User message",
            author=Mock(id=111, name="User", display_name="User", bot=False),
            created_at=datetime.now(timezone.utc),
            channel=Mock(id=123)
        )
        bot_msg = Mock(
            id=2,
            content="Bot message",
            author=Mock(id=222, name="Bot", display_name="Bot", bot=True),
            created_at=datetime.now(timezone.utc),
            channel=Mock(id=123)
        )

        mock_channel = Mock()

        # Create async iterator with mixed messages
        async def mock_history(limit):
            for msg in [user_msg, bot_msg]:
                yield msg

        mock_channel.history = mock_history

        with patch.object(handler, '_resolve_channel', return_value=mock_channel):
            messages = await handler.fetch_messages_from_channel("123456789012345678", 10)

        # Should get both messages but with is_bot flag
        assert len(messages) == 2
        assert messages[0].content == "User message"
        assert messages[0].is_bot is False
        assert messages[1].content == "Bot message"
        assert messages[1].is_bot is True


