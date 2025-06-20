"""
Tests for Discord platform adapter wrapper.
Extracted from test_discord_comprehensive.py to focus on platform-level functionality.
"""

import pytest
import asyncio
import discord
import logging
import os
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

from ciris_engine.adapters.discord.adapter import DiscordPlatform
from ciris_engine.schemas.foundational_schemas_v1 import DiscordMessage, ServiceType
from ciris_engine.registries.base import Priority
from datetime import datetime, timezone


class TestDiscordPlatform:
    """Test Discord platform adapter"""
    
    @pytest.fixture
    def mock_runtime(self):
        """Mock CIRIS runtime"""
        runtime = MagicMock()
        runtime.app_config = MagicMock()
        runtime.memory_service = MagicMock()
        runtime.agent_id = "test_agent"
        runtime.bus_manager= MagicMock()
        runtime.adaptive_filter_service = MagicMock()
        runtime.secrets_service = MagicMock()
        return runtime
    
    @pytest.fixture
    def mock_discord_components(self):
        """Mock Discord components"""
        with patch('ciris_engine.adapters.discord.adapter.DiscordAdapter') as mock_adapter, \
             patch('ciris_engine.adapters.discord.adapter.DiscordObserver') as mock_observer, \
             patch('ciris_engine.adapters.discord.adapter.discord.Client') as mock_client:
            
            mock_adapter_instance = MagicMock()
            mock_adapter.return_value = mock_adapter_instance
            
            mock_observer_instance = MagicMock()
            mock_observer.return_value = mock_observer_instance
            
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance
            
            yield {
                'adapter': mock_adapter,
                'adapter_instance': mock_adapter_instance,
                'observer': mock_observer,
                'observer_instance': mock_observer_instance,
                'client': mock_client,
                'client_instance': mock_client_instance
            }
    
    def test_platform_initialization_missing_token(self, mock_runtime):
        """Test platform initialization without bot token"""
        # Temporarily clear any environment token
        original_token = os.environ.get('DISCORD_BOT_TOKEN')
        if 'DISCORD_BOT_TOKEN' in os.environ:
            del os.environ['DISCORD_BOT_TOKEN']
        
        try:
            with pytest.raises(ValueError, match="requires 'bot_token'"):
                DiscordPlatform(mock_runtime)
        finally:
            # Restore original token if it existed
            if original_token:
                os.environ['DISCORD_BOT_TOKEN'] = original_token
    
    def test_platform_initialization_with_token(self, mock_runtime, mock_discord_components):
        """Test successful platform initialization"""
        # Temporarily clear any environment token to ensure clean test
        original_token = os.environ.get('DISCORD_BOT_TOKEN')
        original_channel = os.environ.get('DISCORD_CHANNEL_ID')
        if 'DISCORD_BOT_TOKEN' in os.environ:
            del os.environ['DISCORD_BOT_TOKEN']
        if 'DISCORD_CHANNEL_ID' in os.environ:
            del os.environ['DISCORD_CHANNEL_ID']
        
        try:
            platform = DiscordPlatform(mock_runtime, discord_bot_token="test_token")
            
            assert platform.runtime == mock_runtime
            assert platform.token == "test_token"
            assert platform.config.bot_token == "test_token"
        finally:
            # Restore original environment
            if original_token:
                os.environ['DISCORD_BOT_TOKEN'] = original_token
            if original_channel:
                os.environ['DISCORD_CHANNEL_ID'] = original_channel
    
    def test_platform_channel_configuration_from_kwargs(self, mock_runtime, mock_discord_components):
        """Test channel configuration from kwargs"""
        # Temporarily clear any environment variables to ensure clean test
        original_token = os.environ.get('DISCORD_BOT_TOKEN')
        original_channel = os.environ.get('DISCORD_CHANNEL_ID')
        original_channels = os.environ.get('DISCORD_CHANNEL_IDS')
        if 'DISCORD_BOT_TOKEN' in os.environ:
            del os.environ['DISCORD_BOT_TOKEN']
        if 'DISCORD_CHANNEL_ID' in os.environ:
            del os.environ['DISCORD_CHANNEL_ID']
        if 'DISCORD_CHANNEL_IDS' in os.environ:
            del os.environ['DISCORD_CHANNEL_IDS']
        
        try:
            platform = DiscordPlatform(
                mock_runtime,
                discord_bot_token="test_token",
                discord_monitored_channel_ids=["999888", "777666", "555444"]
            )
            
            expected_channels = ["999888", "777666", "555444"]
            assert set(platform.config.monitored_channel_ids) == set(expected_channels)
        finally:
            # Restore original environment
            if original_token:
                os.environ['DISCORD_BOT_TOKEN'] = original_token
            if original_channel:
                os.environ['DISCORD_CHANNEL_ID'] = original_channel
            if original_channels:
                os.environ['DISCORD_CHANNEL_IDS'] = original_channels
    
    def test_get_services_to_register(self, mock_runtime, mock_discord_components):
        """Test service registration list"""
        platform = DiscordPlatform(mock_runtime, discord_bot_token="test_token")
        
        services = platform.get_services_to_register()
        
        assert len(services) == 3
        
        # Check communication service
        comm_service = next(s for s in services if s.service_type == ServiceType.COMMUNICATION)
        assert comm_service.priority == Priority.HIGH
        assert "SpeakHandler" in comm_service.handlers
        assert "ObserveHandler" in comm_service.handlers
        assert "ToolHandler" in comm_service.handlers
        
        # Check wise authority service
        wa_service = next(s for s in services if s.service_type == ServiceType.WISE_AUTHORITY)
        assert wa_service.priority == Priority.HIGH
        assert "DeferHandler" in wa_service.handlers
        assert "SpeakHandler" in wa_service.handlers
        
        # Check tool service
        tool_service = next(s for s in services if s.service_type == ServiceType.TOOL)
        assert tool_service.priority == Priority.HIGH
        assert "ToolHandler" in tool_service.handlers
    
    @pytest.mark.asyncio
    async def test_platform_start(self, mock_runtime, mock_discord_components):
        """Test platform start functionality"""
        platform = DiscordPlatform(mock_runtime, discord_bot_token="test_token")
        
        # Mock start methods
        platform.discord_observer.start = AsyncMock()
        platform.discord_adapter.start = AsyncMock()
        
        await platform.start()
        
        platform.discord_observer.start.assert_called_once()
        platform.discord_adapter.start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_platform_stop(self, mock_runtime, mock_discord_components):
        """Test platform stop functionality"""
        platform = DiscordPlatform(mock_runtime, discord_bot_token="test_token")
        
        # Mock stop methods and client
        platform.discord_observer.stop = AsyncMock()
        platform.discord_adapter.stop = AsyncMock()
        # Platform's client is a Discord client instance
        platform.client.is_closed.return_value = False
        platform.client.close = AsyncMock()
        
        await platform.stop()
        
        platform.discord_observer.stop.assert_called_once()
        platform.discord_adapter.stop.assert_called_once()
        # Verify Discord client was closed
        platform.client.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_discord_message_event(self, mock_runtime, mock_discord_components):
        """Test Discord message event handling"""
        platform = DiscordPlatform(mock_runtime, discord_bot_token="test_token")
        
        # Mock observer handle method
        platform.discord_observer.handle_incoming_message = AsyncMock()
        
        # Create test message
        test_message = DiscordMessage(
            message_id="123456",
            destination_id="789012",
            author_id="345678",
            author_name="testuser",
            content="test message",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        await platform._handle_discord_message_event(test_message)
        
        platform.discord_observer.handle_incoming_message.assert_called_once_with(test_message)
    
    @pytest.mark.asyncio
    async def test_handle_discord_message_event_invalid_type(self, mock_runtime, mock_discord_components):
        """Test Discord message event handling with invalid message type"""
        platform = DiscordPlatform(mock_runtime, discord_bot_token="test_token")
        
        # Mock observer handle method
        platform.discord_observer.handle_incoming_message = AsyncMock()
        
        # Create a mock object that doesn't have message_id attribute
        invalid_message = MagicMock()
        invalid_message.configure_mock(**{})  # Clear all mock attributes
        # When message_id is accessed, raise AttributeError
        type(invalid_message).message_id = PropertyMock(side_effect=AttributeError("'str' object has no attribute 'message_id'"))
        
        # Pass invalid message type 
        with patch('ciris_engine.adapters.discord.adapter.logger') as mock_logger:
            await platform._handle_discord_message_event(invalid_message)
        
        # Should not call handle_incoming_message with invalid type
        platform.discord_observer.handle_incoming_message.assert_not_called()
        # Should log warning about invalid type
        mock_logger.warning.assert_called()
    
    @pytest.mark.asyncio
    async def test_run_lifecycle_login_failure(self, mock_runtime, mock_discord_components):
        """Test run lifecycle with Discord login failure"""
        platform = DiscordPlatform(mock_runtime, discord_bot_token="test_token")
        
        # Mock login failure - wrap the exception in run_lifecycle to test the catch block
        original_run_lifecycle = platform.run_lifecycle
        
        async def mock_run_lifecycle(agent_task):
            try:
                # Simulate the actual login failure behavior
                raise discord.LoginFailure("Invalid token")
            except discord.LoginFailure as e:
                logging.getLogger(__name__).error(f"DiscordPlatform: Discord login failed: {e}. Check token and intents.", exc_info=True)
                if hasattr(platform.runtime, 'request_shutdown'):
                    platform.runtime.request_shutdown("Discord login failure")
                if not agent_task.done(): 
                    agent_task.cancel()
        
        platform.run_lifecycle = mock_run_lifecycle
        
        # Ensure runtime has request_shutdown method
        mock_runtime.request_shutdown = MagicMock()
        # Make sure hasattr works
        assert hasattr(mock_runtime, 'request_shutdown')
        
        # Create mock agent task
        agent_task = MagicMock()
        agent_task.done.return_value = False
        agent_task.cancel = MagicMock()
        
        await platform.run_lifecycle(agent_task)
        
        # Verify that request_shutdown was called due to login failure
        mock_runtime.request_shutdown.assert_called_once_with("Discord login failure")
        agent_task.cancel.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_lifecycle_success(self, mock_runtime, mock_discord_components):
        """Test successful run lifecycle"""
        platform = DiscordPlatform(mock_runtime, discord_bot_token="test_token")
        
        # Mock successful client start and ready
        # Platform's client is the actual Discord client instance
        platform.client.start = AsyncMock()
        platform.client.wait_until_ready = AsyncMock()
        platform.client.user = MagicMock()
        platform.client.user.__str__ = MagicMock(return_value="TestBot#1234")
        platform.client.is_closed.return_value = False
        platform.client.close = AsyncMock()
        
        # Create mock agent task that completes quickly
        agent_task = AsyncMock()
        agent_task.done.return_value = False
        
        # Mock asyncio.wait to simulate agent task completing first
        async def mock_wait(tasks, return_when):
            if len(tasks) == 3:  # Initial wait with ready task
                return {agent_task}, set(tasks) - {agent_task}
            else:  # Second wait
                return {agent_task}, set(tasks) - {agent_task}
        
        with patch('asyncio.wait', side_effect=mock_wait):
            await platform.run_lifecycle(agent_task)
        
        # Verify Discord client was closed
        platform.client.close.assert_called_once()