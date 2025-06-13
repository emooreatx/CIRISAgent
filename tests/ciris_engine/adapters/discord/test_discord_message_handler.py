"""Tests for the Discord message handler component."""
import pytest
import discord
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from ciris_engine.adapters.discord.discord_message_handler import DiscordMessageHandler
from ciris_engine.schemas.foundational_schemas_v1 import DiscordMessage, FetchedMessage


class TestDiscordMessageHandler:
    """Test the DiscordMessageHandler class."""

    @pytest.fixture
    def handler(self):
        """Create a message handler instance."""
        return DiscordMessageHandler()

    @pytest.fixture
    def mock_client(self):
        """Create a mock Discord client."""
        client = MagicMock(spec=discord.Client)
        client.wait_until_ready = AsyncMock()
        return client

    @pytest.fixture
    def mock_channel(self):
        """Create a mock Discord channel."""
        channel = MagicMock()
        channel.send = AsyncMock()
        return channel

    @pytest.fixture
    def mock_message(self):
        """Create a mock Discord message."""
        message = MagicMock()
        message.id = 123456789
        message.content = "Test message content"
        message.author.id = 987654321
        message.author.display_name = "TestUser"
        message.author.bot = False
        message.created_at = datetime.now()
        message.channel.id = 555666777
        return message

    def test_initialization(self, handler):
        """Test handler initialization."""
        assert handler.client is None

    def test_set_client(self, handler, mock_client):
        """Test setting the Discord client."""
        handler.set_client(mock_client)
        assert handler.client == mock_client

    @pytest.mark.asyncio
    async def test_send_message_to_channel_success(self, handler, mock_client, mock_channel):
        """Test successful message sending."""
        handler.set_client(mock_client)
        
        with patch.object(handler, '_resolve_channel', return_value=mock_channel):
            await handler.send_message_to_channel("123456", "Test message")
            
            mock_client.wait_until_ready.assert_called_once()
            mock_channel.send.assert_called_once_with("Test message")

    @pytest.mark.asyncio
    async def test_send_message_to_channel_no_client(self, handler):
        """Test message sending without client raises error."""
        with pytest.raises(RuntimeError, match="Discord client is not initialized"):
            await handler.send_message_to_channel("123456", "Test message")

    @pytest.mark.asyncio
    async def test_send_message_to_channel_no_channel(self, handler, mock_client):
        """Test message sending to non-existent channel raises error."""
        handler.set_client(mock_client)
        
        with patch.object(handler, '_resolve_channel', return_value=None):
            with pytest.raises(RuntimeError, match="Discord channel 123456 not found"):
                await handler.send_message_to_channel("123456", "Test message")

    @pytest.mark.asyncio
    async def test_send_message_long_content(self, handler, mock_client, mock_channel):
        """Test sending a long message that needs splitting."""
        handler.set_client(mock_client)
        long_message = "A" * 2000  # Exceeds default max_length of 1950
        
        with patch.object(handler, '_resolve_channel', return_value=mock_channel):
            await handler.send_message_to_channel("123456", long_message)
            
            # Should have been called multiple times for split message
            assert mock_channel.send.call_count > 1

    @pytest.mark.asyncio
    async def test_fetch_messages_from_channel_success(self, handler, mock_client, mock_channel, mock_message):
        """Test successful message fetching."""
        handler.set_client(mock_client)
        
        # Create async iterator for channel history
        async def async_iter():
            yield mock_message
        
        mock_channel.history = MagicMock()
        mock_channel.history.return_value = async_iter()
        
        with patch.object(handler, '_resolve_channel', return_value=mock_channel):
            messages = await handler.fetch_messages_from_channel("123456", 10)
            
            assert len(messages) == 1
            assert isinstance(messages[0], FetchedMessage)
            assert messages[0].message_id == str(mock_message.id)
            assert messages[0].content == mock_message.content

    @pytest.mark.asyncio
    async def test_fetch_messages_from_channel_no_client(self, handler):
        """Test message fetching without client raises error."""
        with pytest.raises(RuntimeError, match="Discord client is not initialized"):
            await handler.fetch_messages_from_channel("123456", 10)

    @pytest.mark.asyncio
    async def test_fetch_messages_from_channel_no_channel(self, handler, mock_client):
        """Test message fetching from non-existent channel returns empty list."""
        handler.set_client(mock_client)
        
        with patch.object(handler, '_resolve_channel', return_value=None):
            messages = await handler.fetch_messages_from_channel("123456", 10)
            assert messages == []

    @pytest.mark.asyncio
    async def test_fetch_messages_no_history_attribute(self, handler, mock_client):
        """Test message fetching from channel without history returns empty list."""
        handler.set_client(mock_client)
        mock_channel = MagicMock()
        # Channel without history attribute
        if hasattr(mock_channel, 'history'):
            delattr(mock_channel, 'history')
        
        with patch.object(handler, '_resolve_channel', return_value=mock_channel):
            messages = await handler.fetch_messages_from_channel("123456", 10)
            assert messages == []

    def test_convert_to_discord_message(self, handler, mock_message):
        """Test converting discord.py message to DiscordMessage schema."""
        mock_message.channel = MagicMock()
        mock_message.channel.id = 555666777
        
        # Mock DMChannel for is_dm test
        with patch('discord.DMChannel') as mock_dm_channel:
            mock_message.channel.__class__ = mock_dm_channel
            discord_msg = handler.convert_to_discord_message(mock_message)
            
            assert isinstance(discord_msg, DiscordMessage)
            assert discord_msg.message_id == str(mock_message.id)
            assert discord_msg.content == mock_message.content
            assert discord_msg.author_id == str(mock_message.author.id)
            assert discord_msg.author_name == mock_message.author.display_name
            assert discord_msg.channel_id == str(mock_message.channel.id)
            assert discord_msg.is_bot == mock_message.author.bot
            assert discord_msg.raw_message == mock_message

    def test_split_message_short(self, handler):
        """Test splitting a short message returns single chunk."""
        content = "Short message"
        chunks = handler._split_message(content)
        assert len(chunks) == 1
        assert chunks[0] == content

    def test_split_message_long(self, handler):
        """Test splitting a long message returns multiple chunks."""
        content = "A" * 2000  # Longer than default max_length
        chunks = handler._split_message(content, max_length=100)
        assert len(chunks) > 1
        # Verify no chunk exceeds max_length
        for chunk in chunks:
            assert len(chunk) <= 100

    def test_split_message_with_newlines(self, handler):
        """Test splitting message with newlines preserves structure."""
        content = "Line 1\n" + "B" * 100 + "\nLine 3"
        chunks = handler._split_message(content, max_length=50)
        
        # Should split appropriately
        assert len(chunks) >= 2

    def test_split_message_very_long_line(self, handler):
        """Test splitting message with a single very long line."""
        content = "A" * 200  # Single long line
        chunks = handler._split_message(content, max_length=50)
        
        assert len(chunks) == 4  # 200/50 = 4 chunks
        for chunk in chunks:
            assert len(chunk) <= 50

    @pytest.mark.asyncio
    async def test_resolve_channel_success(self, handler, mock_client, mock_channel):
        """Test successful channel resolution."""
        handler.set_client(mock_client)
        mock_client.get_channel.return_value = mock_channel
        
        result = await handler._resolve_channel("123456")
        assert result == mock_channel
        mock_client.get_channel.assert_called_once_with(123456)

    @pytest.mark.asyncio
    async def test_resolve_channel_fetch_fallback(self, handler, mock_client, mock_channel):
        """Test channel resolution with fetch fallback."""
        handler.set_client(mock_client)
        mock_client.get_channel.return_value = None  # Not in cache
        mock_client.fetch_channel = AsyncMock(return_value=mock_channel)
        
        result = await handler._resolve_channel("123456")
        assert result == mock_channel
        mock_client.fetch_channel.assert_called_once_with(123456)

    @pytest.mark.asyncio
    async def test_resolve_channel_invalid_id(self, handler, mock_client):
        """Test channel resolution with invalid ID."""
        handler.set_client(mock_client)
        
        result = await handler._resolve_channel("invalid_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_channel_not_found(self, handler, mock_client):
        """Test channel resolution when channel doesn't exist."""
        handler.set_client(mock_client)
        mock_client.get_channel.return_value = None
        mock_client.fetch_channel = AsyncMock(side_effect=discord.NotFound(MagicMock(), "Channel not found"))
        
        result = await handler._resolve_channel("123456")
        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_channel_forbidden(self, handler, mock_client):
        """Test channel resolution when access is forbidden."""
        handler.set_client(mock_client)
        mock_client.get_channel.return_value = None
        mock_client.fetch_channel = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "Access denied"))
        
        result = await handler._resolve_channel("123456")
        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_channel_no_client(self, handler):
        """Test channel resolution without client."""
        result = await handler._resolve_channel("123456")
        assert result is None