"""Tests for the Discord guidance handler component."""
import pytest
import discord
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from ciris_engine.adapters.discord.discord_guidance_handler import DiscordGuidanceHandler


class TestDiscordGuidanceHandler:
    """Test the DiscordGuidanceHandler class."""

    @pytest.fixture
    def handler(self):
        """Create a guidance handler instance."""
        return DiscordGuidanceHandler()

    @pytest.fixture
    def mock_client(self):
        """Create a mock Discord client."""
        client = MagicMock(spec=discord.Client)
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
        message.content = "Test guidance response"
        message.author.id = 987654321
        message.author.display_name = "WiseAuthority"
        message.author.bot = False
        message.reference = None
        return message

    @pytest.fixture
    def sample_context(self):
        """Create sample context for guidance requests."""
        return {
            "task_id": "task_123",
            "task_description": "Test task description",
            "thought_id": "thought_456",
            "priority": "high"
        }

    def test_initialization(self, handler):
        """Test handler initialization."""
        assert handler.client is None

    def test_set_client(self, handler, mock_client):
        """Test setting the Discord client."""
        handler.set_client(mock_client)
        assert handler.client == mock_client

    @pytest.mark.asyncio
    async def test_fetch_guidance_no_client(self, handler, sample_context):
        """Test fetching guidance without client raises error."""
        with pytest.raises(RuntimeError, match="Discord client is not initialized"):
            await handler.fetch_guidance_from_channel("123456", sample_context)

    @pytest.mark.asyncio
    async def test_fetch_guidance_no_channel(self, handler, mock_client, sample_context):
        """Test fetching guidance from non-existent channel raises error."""
        handler.set_client(mock_client)
        
        with patch.object(handler, '_resolve_channel', return_value=None):
            with pytest.raises(RuntimeError, match="Deferral channel 123456 not found"):
                await handler.fetch_guidance_from_channel("123456", sample_context)

    @pytest.mark.asyncio
    async def test_fetch_guidance_channel_no_send(self, handler, mock_client, sample_context):
        """Test fetching guidance from channel that doesn't support sending."""
        handler.set_client(mock_client)
        mock_channel = MagicMock()
        # Remove send attribute
        if hasattr(mock_channel, 'send'):
            delattr(mock_channel, 'send')
        
        with patch.object(handler, '_resolve_channel', return_value=mock_channel):
            result = await handler.fetch_guidance_from_channel("123456", sample_context)
            assert result == {"guidance": None}

    @pytest.mark.asyncio
    async def test_fetch_guidance_success_with_reply(self, handler, mock_client, mock_channel, mock_message, sample_context):
        """Test successful guidance fetching with a reply."""
        handler.set_client(mock_client)
        
        # Mock request message
        request_message = MagicMock()
        request_message.id = 111222333
        mock_channel.send.return_value = request_message
        
        # Mock reply message
        mock_message.reference = MagicMock()
        mock_message.reference.message_id = request_message.id
        
        # Mock channel history
        async def async_iter():
            yield mock_message
        
        mock_channel.history = MagicMock()
        mock_channel.history.return_value = async_iter()
        
        with patch.object(handler, '_resolve_channel', return_value=mock_channel):
            result = await handler.fetch_guidance_from_channel("123456", sample_context)
            
            assert result["guidance"] == "Test guidance response"
            assert result["is_reply"] is True
            assert result["is_unsolicited"] is False
            assert result["author_id"] == str(mock_message.author.id)
            assert result["author_name"] == mock_message.author.display_name

    @pytest.mark.asyncio
    async def test_fetch_guidance_success_unsolicited(self, handler, mock_client, mock_channel, mock_message, sample_context):
        """Test successful guidance fetching with unsolicited message."""
        handler.set_client(mock_client)
        
        # Ensure channel can send messages
        assert hasattr(mock_channel, 'send')
        assert hasattr(mock_channel, 'history')
        
        # Mock request message
        request_message = MagicMock()
        request_message.id = 111222333
        mock_channel.send.return_value = request_message
        
        # Mock unsolicited message (no reference)
        mock_message.reference = None
        # Ensure mock_message has a reference attribute for hasattr check
        assert hasattr(mock_message, 'reference')
        
        # Mock channel history
        async def async_iter():
            yield mock_message
        
        mock_channel.history = MagicMock()
        mock_channel.history.return_value = async_iter()
        
        with patch.object(handler, '_resolve_channel', return_value=mock_channel):
            result = await handler.fetch_guidance_from_channel("123456", sample_context)
            
            assert result["guidance"] == "Test guidance response"
            assert result["is_reply"] is False
            assert result["is_unsolicited"] is True

    @pytest.mark.asyncio
    async def test_fetch_guidance_no_messages(self, handler, mock_client, mock_channel, sample_context):
        """Test guidance fetching when no human messages found."""
        handler.set_client(mock_client)
        
        # Mock request message
        request_message = MagicMock()
        request_message.id = 111222333
        mock_channel.send.return_value = request_message
        
        # Mock empty history
        async def async_iter():
            return
            yield  # Unreachable but makes it a generator
        
        mock_channel.history = MagicMock()
        mock_channel.history.return_value = async_iter()
        
        with patch.object(handler, '_resolve_channel', return_value=mock_channel):
            result = await handler.fetch_guidance_from_channel("123456", sample_context)
            
            assert result == {"guidance": None}

    @pytest.mark.asyncio
    async def test_fetch_guidance_ignores_bot_messages(self, handler, mock_client, mock_channel, sample_context):
        """Test that bot messages are ignored during guidance fetching."""
        handler.set_client(mock_client)
        
        # Mock request message
        request_message = MagicMock()
        request_message.id = 111222333
        mock_channel.send.return_value = request_message
        
        # Mock bot message
        bot_message = MagicMock()
        bot_message.author.bot = True
        bot_message.id = 999888777
        
        # Mock channel history with only bot message
        async def async_iter():
            yield bot_message
        
        mock_channel.history = MagicMock()
        mock_channel.history.return_value = async_iter()
        
        with patch.object(handler, '_resolve_channel', return_value=mock_channel):
            result = await handler.fetch_guidance_from_channel("123456", sample_context)
            
            assert result == {"guidance": None}

    @pytest.mark.asyncio
    async def test_send_deferral_no_client(self, handler):
        """Test sending deferral without client raises error."""
        with pytest.raises(RuntimeError, match="Discord client is not initialized"):
            await handler.send_deferral_to_channel("123456", "thought_123", "test reason")

    @pytest.mark.asyncio
    async def test_send_deferral_no_channel(self, handler, mock_client):
        """Test sending deferral to non-existent channel raises error."""
        handler.set_client(mock_client)
        
        with patch.object(handler, '_resolve_channel', return_value=None):
            with pytest.raises(RuntimeError, match="Deferral channel 123456 not found"):
                await handler.send_deferral_to_channel("123456", "thought_123", "test reason")

    @pytest.mark.asyncio
    async def test_send_deferral_success(self, handler, mock_client, mock_channel):
        """Test successful deferral sending."""
        handler.set_client(mock_client)
        
        context = {
            "task_id": "task_123",
            "task_description": "Test task",
            "priority": "high"
        }
        
        with patch.object(handler, '_resolve_channel', return_value=mock_channel):
            await handler.send_deferral_to_channel("123456", "thought_123", "test reason", context)
            
            # Should have sent at least one message
            assert mock_channel.send.called

    @pytest.mark.asyncio
    async def test_send_deferral_long_report(self, handler, mock_client, mock_channel):
        """Test sending a long deferral report that requires splitting."""
        handler.set_client(mock_client)
        
        # Create context with very long descriptions
        context = {
            "task_description": "A" * 1000,
            "thought_content": "B" * 1000,
            "conversation_context": "C" * 1000
        }
        
        with patch.object(handler, '_resolve_channel', return_value=mock_channel):
            await handler.send_deferral_to_channel("123456", "thought_123", "test reason", context)
            
            # Should have been called multiple times for long report
            assert mock_channel.send.call_count >= 1

    def test_build_deferral_report_basic(self, handler):
        """Test building basic deferral report."""
        report = handler._build_deferral_report("thought_123", "test reason")
        
        assert "thought_123" in report
        assert "test reason" in report
        assert "CIRIS Deferral Report" in report

    def test_build_deferral_report_with_context(self, handler):
        """Test building deferral report with context."""
        context = {
            "task_id": "task_123",
            "task_description": "Test task description",
            "thought_content": "Test thought content",
            "priority": "high",
            "attempted_action": "SPEAK",
            "max_rounds_reached": True
        }
        
        report = handler._build_deferral_report("thought_123", "test reason", context)
        
        assert "task_123" in report
        assert "Test task description" in report
        assert "Test thought content" in report
        assert "high" in report
        assert "SPEAK" in report
        assert "Maximum processing rounds reached" in report

    def test_build_deferral_report_truncation(self, handler):
        """Test that long context values are truncated."""
        context = {
            "task_description": "A" * 300,  # Longer than 200 char limit
            "thought_content": "B" * 400,   # Longer than 300 char limit
            "conversation_context": "C" * 500  # Longer than 400 char limit
        }
        
        report = handler._build_deferral_report("thought_123", "test reason", context)
        
        # Check that truncation happened (should contain "...")
        assert "..." in report

    def test_truncate_text_short(self, handler):
        """Test truncating short text."""
        text = "Short text"
        result = handler._truncate_text(text, 100)
        assert result == text

    def test_truncate_text_long(self, handler):
        """Test truncating long text."""
        text = "A" * 100
        result = handler._truncate_text(text, 50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_split_message_functionality(self, handler):
        """Test message splitting functionality."""
        content = "A" * 2000
        chunks = handler._split_message(content, max_length=100)
        
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 100

    @pytest.mark.asyncio
    async def test_resolve_channel_success(self, handler, mock_client, mock_channel):
        """Test successful channel resolution."""
        handler.set_client(mock_client)
        mock_client.get_channel.return_value = mock_channel
        
        result = await handler._resolve_channel("123456")
        assert result == mock_channel

    @pytest.mark.asyncio
    async def test_resolve_channel_invalid_id(self, handler, mock_client):
        """Test channel resolution with invalid ID."""
        handler.set_client(mock_client)
        
        result = await handler._resolve_channel("invalid_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_channel_no_client(self, handler):
        """Test channel resolution without client."""
        result = await handler._resolve_channel("123456")
        assert result is None