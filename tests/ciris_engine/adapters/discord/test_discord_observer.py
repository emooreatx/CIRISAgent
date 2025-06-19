"""
Tests for Discord observer functionality.
Extracted from test_discord_comprehensive.py to focus on message observation and processing.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

from ciris_engine.adapters.discord.discord_observer import DiscordObserver
from ciris_engine.schemas.foundational_schemas_v1 import DiscordMessage


class TestDiscordObserver:
    """Test Discord observer functionality"""
    
    @pytest.fixture
    def mock_services(self):
        """Mock services for observer"""
        return {
            'memory_service': MagicMock(),
            'agent_id': '12345',  # Bot's user ID
            'bus_manager': MagicMock(),
            'filter_service': MagicMock(),
            'secrets_service': MagicMock(),
            'communication_service': MagicMock()
        }
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration manager"""
        with patch('ciris_engine.config.config_manager.get_config') as mock_get_config:
            mock_config_obj = MagicMock()
            mock_get_config.return_value = mock_config_obj
            yield mock_config_obj
    
    def test_observer_initialization_with_channels(self, mock_services, mock_config):
        """Test observer initialization with explicit channels"""
        observer = DiscordObserver(
            monitored_channel_ids=["123456", "789012"],
            deferral_channel_id="567890",
            wa_user_ids=["537080239679864862"],
            **mock_services
        )
        
        assert observer.monitored_channel_ids == ["123456", "789012"]
        assert observer.deferral_channel_id == "567890"
        assert observer.wa_user_ids == ["537080239679864862"]
        assert observer.memory_service == mock_services['memory_service']
        assert observer.agent_id == mock_services['agent_id']
        assert observer.communication_service == mock_services['communication_service']
    
    def test_observer_initialization_from_config(self, mock_services, mock_config):
        """Test observer initialization using config manager"""
        observer = DiscordObserver(**mock_services)
        
        # Should use empty defaults when no channels provided
        assert observer.monitored_channel_ids == []
        assert observer.deferral_channel_id is None
        assert observer.wa_user_ids == []
    
    def test_observer_initialization_legacy_single_channel(self, mock_services, mock_config):
        """Test observer initialization with single channel in list"""
        # Observer should use provided channel list
        observer = DiscordObserver(
            monitored_channel_ids=["999888"],
            **mock_services
        )
        
        assert observer.monitored_channel_ids == ["999888"]
    
    @pytest.mark.asyncio
    async def test_start_and_stop(self, mock_services, mock_config):
        """Test observer start and stop methods"""
        observer = DiscordObserver(
            monitored_channel_ids=["123456"],
            **mock_services
        )
        
        await observer.start()
        await observer.stop()
        # Should not raise any exceptions
    
    @pytest.mark.asyncio
    async def test_handle_incoming_message_valid_channel(self, mock_services, mock_config):
        """Test handling incoming Discord message from monitored channel"""
        observer = DiscordObserver(
            monitored_channel_ids=["123456"],
            **mock_services
        )
        
        # Mock the processing methods
        observer._process_message_secrets = AsyncMock(side_effect=lambda x: x)
        observer._apply_message_filtering = AsyncMock()
        observer._handle_passive_observation = AsyncMock()
        observer._recall_context = AsyncMock()
        observer._history = []
        
        # Mock filter result
        filter_result = MagicMock()
        filter_result.should_process = True
        filter_result.priority.value = 'medium'
        filter_result.context_hints = {}
        filter_result.reasoning = "test reasoning"
        observer._apply_message_filtering.return_value = filter_result
        
        test_message = DiscordMessage(
            message_id="msg123",
            channel_id="123456",
            author_id="user456",  # Not agent's message
            author_name="testuser",
            content="test message",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        await observer.handle_incoming_message(test_message)
        
        # Verify message was processed
        observer._process_message_secrets.assert_called_once()
        observer._apply_message_filtering.assert_called_once()
        observer._handle_passive_observation.assert_called_once()
        observer._recall_context.assert_called_once()
        assert len(observer._history) == 1
    
    @pytest.mark.asyncio
    async def test_handle_incoming_message_deferral_channel(self, mock_services, mock_config):
        """Test handling message from deferral channel"""
        observer = DiscordObserver(
            monitored_channel_ids=["123456"],
            deferral_channel_id="567890",
            **mock_services
        )
        
        # Mock processing methods
        observer._process_message_secrets = AsyncMock(side_effect=lambda x: x)
        observer._apply_message_filtering = AsyncMock()
        observer._handle_passive_observation = AsyncMock()
        observer._recall_context = AsyncMock()
        observer._history = []
        
        filter_result = MagicMock()
        filter_result.should_process = True
        filter_result.priority.value = 'medium'
        filter_result.context_hints = {}
        filter_result.reasoning = "test reasoning"
        observer._apply_message_filtering.return_value = filter_result
        
        # Message from deferral channel (567890)
        test_message = DiscordMessage(
            message_id="msg123",
            channel_id="567890",  # Deferral channel
            author_id="user456",
            author_name="testuser",
            content="deferral message",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        await observer.handle_incoming_message(test_message)
        
        # Should still process deferral messages
        observer._process_message_secrets.assert_called_once()
        observer._apply_message_filtering.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_incoming_message_agent_message(self, mock_services, mock_config):
        """Test handling agent's own message"""
        observer = DiscordObserver(
            monitored_channel_ids=["123456"],
            **mock_services
        )
        
        observer._process_message_secrets = AsyncMock(side_effect=lambda x: x)
        observer._apply_message_filtering = AsyncMock()
        observer._handle_passive_observation = AsyncMock()
        observer._history = []
        
        # Agent's own message
        test_message = DiscordMessage(
            message_id="msg123",
            channel_id="123456",
            author_id="12345",  # Agent's ID
            author_name="CIRIS Bot",
            content="agent response",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        await observer.handle_incoming_message(test_message)
        
        # Should add to history but not process further
        observer._process_message_secrets.assert_called_once()
        assert len(observer._history) == 1
        observer._apply_message_filtering.assert_not_called()
        observer._handle_passive_observation.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_incoming_message_wrong_channel(self, mock_services, mock_config):
        """Test handling message from non-monitored channel"""
        observer = DiscordObserver(
            monitored_channel_ids=["123456"],
            **mock_services
        )
        
        observer._process_message_secrets = AsyncMock()
        
        test_message = DiscordMessage(
            message_id="msg123",
            channel_id="999999",  # Not monitored
            author_id="user456",
            author_name="testuser",
            content="ignored message",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        await observer.handle_incoming_message(test_message)
        
        # Should not process message from non-monitored channel
        observer._process_message_secrets.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_incoming_message_invalid_type(self, mock_services, mock_config):
        """Test handling invalid message type"""
        observer = DiscordObserver(
            monitored_channel_ids=["123456"],
            **mock_services
        )
        
        observer._process_message_secrets = AsyncMock()
        
        # Pass invalid message type
        await observer.handle_incoming_message("not_a_discord_message")
        
        # Should not process invalid message type
        observer._process_message_secrets.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_incoming_message_filtered_out(self, mock_services, mock_config):
        """Test handling message that gets filtered out"""
        observer = DiscordObserver(
            monitored_channel_ids=["123456"],
            **mock_services
        )
        
        observer._process_message_secrets = AsyncMock(side_effect=lambda x: x)
        observer._apply_message_filtering = AsyncMock()
        observer._handle_passive_observation = AsyncMock()
        observer._history = []
        
        # Mock filter result that rejects message
        filter_result = MagicMock()
        filter_result.should_process = False
        filter_result.reasoning = "spam detected"
        observer._apply_message_filtering.return_value = filter_result
        
        test_message = DiscordMessage(
            message_id="msg123",
            channel_id="123456",
            author_id="user456",
            author_name="testuser",
            content="spam message",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        await observer.handle_incoming_message(test_message)
        
        # Should process secrets but not handle observation
        observer._process_message_secrets.assert_called_once()
        observer._apply_message_filtering.assert_called_once()
        observer._handle_passive_observation.assert_not_called()
        assert len(observer._history) == 1
    
    @pytest.mark.asyncio
    async def test_handle_incoming_message_high_priority(self, mock_services, mock_config):
        """Test handling high priority message"""
        observer = DiscordObserver(
            monitored_channel_ids=["123456"],
            **mock_services
        )
        
        observer._process_message_secrets = AsyncMock(side_effect=lambda x: x)
        observer._apply_message_filtering = AsyncMock()
        observer._handle_priority_observation = AsyncMock()
        observer._recall_context = AsyncMock()
        observer._history = []
        
        # Mock high priority filter result
        filter_result = MagicMock()
        filter_result.should_process = True
        filter_result.priority.value = 'high'
        filter_result.context_hints = {"urgent": True}
        filter_result.reasoning = "urgent request detected"
        observer._apply_message_filtering.return_value = filter_result
        
        test_message = DiscordMessage(
            message_id="msg123",
            channel_id="123456",
            author_id="user456",
            author_name="testuser",
            content="URGENT: help needed",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        await observer.handle_incoming_message(test_message)
        
        # Should handle as priority observation
        observer._handle_priority_observation.assert_called_once()
        observer._recall_context.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_deferral_message_success(self, mock_services, mock_config):
        """Test sending deferral message successfully"""
        observer = DiscordObserver(
            monitored_channel_ids=["123456"],
            **mock_services
        )
        
        # Mock communication service
        mock_comm = mock_services['communication_service']
        mock_comm.send_message = AsyncMock()
        
        # Set up deferral channel for test
        observer.deferral_channel_id = "567890"
        
        await observer._send_deferral_message("Test deferral content")
        
        mock_comm.send_message.assert_called_once_with("567890", "Test deferral content")
    
    @pytest.mark.asyncio
    async def test_send_deferral_message_no_service(self, mock_services, mock_config):
        """Test sending deferral message without communication service"""
        observer = DiscordObserver(
            monitored_channel_ids=["123456"],
            communication_service=None,
            **{k: v for k, v in mock_services.items() if k != 'communication_service'}
        )
        
        # Should not raise exception
        await observer._send_deferral_message("Test content")
    
    @pytest.mark.asyncio
    async def test_send_deferral_message_no_channel_configured(self, mock_services, mock_config):
        """Test sending deferral message without deferral channel configured"""
        observer = DiscordObserver(
            monitored_channel_ids=["123456"],
            **mock_services
        )
        
        # Ensure no deferral channel is set
        observer.deferral_channel_id = None
        
        mock_comm = mock_services['communication_service']
        mock_comm.send_message = AsyncMock()
        
        await observer._send_deferral_message("Test content")
        
        # Should not attempt to send
        mock_comm.send_message.assert_not_called()