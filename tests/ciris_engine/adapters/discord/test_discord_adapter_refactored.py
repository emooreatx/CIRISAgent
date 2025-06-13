"""Tests for the refactored Discord adapter."""
import pytest
import discord
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from ciris_engine.adapters.discord.discord_adapter import DiscordAdapter
from ciris_engine.schemas.foundational_schemas_v1 import DiscordMessage, FetchedMessage
from ciris_engine.protocols.services import CommunicationService, WiseAuthorityService, ToolService


class TestDiscordAdapterRefactored:
    """Test the refactored DiscordAdapter class."""

    @pytest.fixture
    def adapter(self):
        """Create a Discord adapter instance."""
        return DiscordAdapter("fake_token")

    @pytest.fixture
    def mock_client(self):
        """Create a mock Discord client."""
        client = MagicMock(spec=discord.Client)
        client.is_closed.return_value = False
        return client

    @pytest.fixture
    def mock_tool_registry(self):
        """Create a mock tool registry."""
        registry = MagicMock()
        registry.tools = {"test_tool": MagicMock()}
        return registry

    @pytest.fixture
    def mock_callback(self):
        """Create a mock message callback."""
        return AsyncMock()

    def test_initialization_basic(self, adapter):
        """Test basic adapter initialization."""
        assert adapter.token == "fake_token"
        assert adapter.client is None
        assert isinstance(adapter, CommunicationService)
        assert isinstance(adapter, WiseAuthorityService)
        assert isinstance(adapter, ToolService)

    def test_initialization_with_params(self, mock_client, mock_tool_registry, mock_callback):
        """Test adapter initialization with parameters."""
        adapter = DiscordAdapter("test_token", mock_tool_registry, mock_client, mock_callback)
        
        assert adapter.token == "test_token"
        assert adapter.client == mock_client
        assert adapter._channel_manager.client == mock_client
        assert adapter._message_handler.client == mock_client
        assert adapter._guidance_handler.client == mock_client
        assert adapter._tool_handler.client == mock_client

    def test_client_property(self, adapter, mock_client):
        """Test client property access."""
        assert adapter.client is None
        
        adapter._channel_manager.set_client(mock_client)
        assert adapter.client == mock_client

    @pytest.mark.asyncio
    async def test_send_message_success(self, adapter, mock_client):
        """Test successful message sending."""
        adapter._channel_manager.set_client(mock_client)
        
        with patch.object(adapter, 'retry_with_backoff', new_callable=AsyncMock) as mock_retry:
            with patch('ciris_engine.adapters.discord.discord_adapter.persistence') as mock_persistence:
                result = await adapter.send_message("123456", "Test message")
                
                assert result is True
                mock_retry.assert_called_once()
                mock_persistence.add_correlation.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_failure(self, adapter, mock_client):
        """Test message sending failure."""
        adapter._channel_manager.set_client(mock_client)
        
        with patch.object(adapter, 'retry_with_backoff', side_effect=Exception("Send failed")):
            result = await adapter.send_message("123456", "Test message")
            assert result is False

    @pytest.mark.asyncio
    async def test_fetch_messages_success(self, adapter, mock_client):
        """Test successful message fetching."""
        adapter._channel_manager.set_client(mock_client)
        expected_messages = [FetchedMessage(
            id="123", content="test", author_id="456", author_name="user",
            timestamp="2023-01-01T00:00:00", is_bot=False
        )]
        
        with patch.object(adapter, 'retry_with_backoff', return_value=expected_messages):
            result = await adapter.fetch_messages("123456", 10)
            assert result == expected_messages

    @pytest.mark.asyncio
    async def test_fetch_messages_failure(self, adapter, mock_client):
        """Test message fetching failure."""
        adapter._channel_manager.set_client(mock_client)
        
        with patch.object(adapter, 'retry_with_backoff', side_effect=Exception("Fetch failed")):
            result = await adapter.fetch_messages("123456", 10)
            assert result == []

    @pytest.mark.asyncio
    async def test_fetch_guidance_success(self, adapter, mock_client):
        """Test successful guidance fetching."""
        adapter._channel_manager.set_client(mock_client)
        context = {"task": "test task"}
        expected_guidance = {"guidance": "Test guidance response"}
        
        with patch.object(adapter, 'retry_with_backoff', return_value=expected_guidance):
            with patch('ciris_engine.config.config_manager.get_config') as mock_get_config:
                mock_config = MagicMock()
                mock_config.discord_deferral_channel_id = "987654"
                mock_get_config.return_value = mock_config
                
                with patch('ciris_engine.adapters.discord.discord_adapter.persistence'):
                    result = await adapter.fetch_guidance(context)
                    assert result == "Test guidance response"

    @pytest.mark.asyncio
    async def test_fetch_guidance_no_channel_config(self, adapter, mock_client):
        """Test guidance fetching without channel configuration."""
        adapter._channel_manager.set_client(mock_client)
        
        with patch('ciris_engine.config.config_manager.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.discord_deferral_channel_id = None
            mock_get_config.return_value = mock_config
            
            with pytest.raises(RuntimeError, match="Guidance channel not configured"):
                await adapter.fetch_guidance({"task": "test"})

    @pytest.mark.asyncio
    async def test_send_deferral_success(self, adapter, mock_client):
        """Test successful deferral sending."""
        adapter._channel_manager.set_client(mock_client)
        
        with patch.object(adapter, 'retry_with_backoff', new_callable=AsyncMock):
            with patch('ciris_engine.config.config_manager.get_config') as mock_get_config:
                mock_config = MagicMock()
                mock_config.discord_deferral_channel_id = "987654"
                mock_get_config.return_value = mock_config
                
                with patch('ciris_engine.adapters.discord.discord_adapter.persistence'):
                    result = await adapter.send_deferral("thought_123", "test reason", {"context": "data"})
                    assert result is True

    @pytest.mark.asyncio
    async def test_send_deferral_no_channel_config(self, adapter, mock_client):
        """Test deferral sending without channel configuration."""
        adapter._channel_manager.set_client(mock_client)
        
        with patch('ciris_engine.config.config_manager.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.discord_deferral_channel_id = None
            mock_get_config.return_value = mock_config
            
            result = await adapter.send_deferral("thought_123", "test reason")
            assert result is False

    @pytest.mark.asyncio
    async def test_execute_tool_success(self, adapter, mock_client):
        """Test successful tool execution."""
        adapter._channel_manager.set_client(mock_client)
        expected_result = {"status": "success", "data": "test"}
        
        with patch.object(adapter, 'retry_with_backoff', return_value=expected_result):
            result = await adapter.execute_tool("test_tool", {"param": "value"})
            assert result == expected_result

    @pytest.mark.asyncio
    async def test_get_tool_result(self, adapter):
        """Test tool result retrieval."""
        expected_result = {"status": "success"}
        
        with patch.object(adapter._tool_handler, 'get_tool_result', return_value=expected_result):
            result = await adapter.get_tool_result("correlation_123", 30.0)
            assert result == expected_result

    @pytest.mark.asyncio
    async def test_get_available_tools(self, adapter):
        """Test getting available tools."""
        expected_tools = ["tool1", "tool2"]
        
        with patch.object(adapter._tool_handler, 'get_available_tools', return_value=expected_tools):
            result = await adapter.get_available_tools()
            assert result == expected_tools

    @pytest.mark.asyncio
    async def test_validate_parameters(self, adapter):
        """Test parameter validation."""
        with patch.object(adapter._tool_handler, 'validate_tool_parameters', return_value=True):
            result = await adapter.validate_parameters("test_tool", {"param": "value"})
            assert result is True

    @pytest.mark.asyncio
    async def test_get_capabilities(self, adapter):
        """Test getting service capabilities."""
        with patch.object(CommunicationService, 'get_capabilities', return_value=["send_message", "fetch_messages"]):
            capabilities = await adapter.get_capabilities()
            
            # Should include capabilities from all three service types
            assert "send_message" in capabilities
            assert "fetch_messages" in capabilities
            assert "fetch_guidance" in capabilities
            assert "send_deferral" in capabilities
            assert "execute_tool" in capabilities
            assert "get_available_tools" in capabilities
            assert "get_tool_result" in capabilities
            assert "validate_parameters" in capabilities

    @pytest.mark.asyncio
    async def test_send_output(self, adapter, mock_client):
        """Test sending output."""
        adapter._channel_manager.set_client(mock_client)
        
        with patch.object(adapter, 'retry_with_backoff', new_callable=AsyncMock) as mock_retry:
            await adapter.send_output("123456", "Test output")
            mock_retry.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_message(self, adapter, mock_client):
        """Test message handling."""
        adapter._channel_manager.set_client(mock_client)
        mock_message = MagicMock()
        
        with patch.object(adapter._channel_manager, 'on_message', new_callable=AsyncMock) as mock_on_message:
            await adapter.on_message(mock_message)
            mock_on_message.assert_called_once_with(mock_message)

    def test_attach_to_client(self, adapter, mock_client):
        """Test attaching to a Discord client."""
        with patch.object(adapter._channel_manager, 'set_client') as mock_set_client:
            with patch.object(adapter._message_handler, 'set_client') as mock_msg_set:
                with patch.object(adapter._guidance_handler, 'set_client') as mock_guide_set:
                    with patch.object(adapter._tool_handler, 'set_client') as mock_tool_set:
                        with patch.object(adapter._channel_manager, 'attach_to_client') as mock_attach:
                            adapter.attach_to_client(mock_client)
                            
                            mock_set_client.assert_called_once_with(mock_client)
                            mock_msg_set.assert_called_once_with(mock_client)
                            mock_guide_set.assert_called_once_with(mock_client)
                            mock_tool_set.assert_called_once_with(mock_client)
                            mock_attach.assert_called_once_with(mock_client)

    @pytest.mark.asyncio
    async def test_start_with_client(self, adapter, mock_client):
        """Test starting adapter with existing client."""
        adapter._channel_manager.set_client(mock_client)
        
        with patch.object(adapter.__class__.__bases__[0], 'start', new_callable=AsyncMock) as mock_super_start:
            await adapter.start()
            mock_super_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_without_client(self, adapter):
        """Test starting adapter without client."""
        with patch.object(adapter.__class__.__bases__[0], 'start', new_callable=AsyncMock) as mock_super_start:
            await adapter.start()
            mock_super_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_failure(self, adapter):
        """Test adapter start failure."""
        with patch.object(adapter.__class__.__bases__[0], 'start', side_effect=Exception("Start failed")):
            with pytest.raises(Exception, match="Start failed"):
                await adapter.start()

    @pytest.mark.asyncio
    async def test_stop_success(self, adapter):
        """Test successful adapter stop."""
        with patch.object(adapter._tool_handler, 'clear_tool_results') as mock_clear:
            with patch.object(adapter.__class__.__bases__[0], 'stop', new_callable=AsyncMock) as mock_super_stop:
                await adapter.stop()
                
                mock_clear.assert_called_once()
                mock_super_stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_failure(self, adapter):
        """Test adapter stop with failure."""
        with patch.object(adapter._tool_handler, 'clear_tool_results'):
            with patch.object(adapter.__class__.__bases__[0], 'stop', side_effect=Exception("Stop failed")):
                # Should not raise - exception is logged
                await adapter.stop()

    @pytest.mark.asyncio
    async def test_is_healthy_success(self, adapter, mock_client):
        """Test successful health check."""
        adapter._channel_manager.set_client(mock_client)
        
        with patch.object(adapter._channel_manager, 'is_client_ready', return_value=True):
            result = await adapter.is_healthy()
            assert result is True

    @pytest.mark.asyncio
    async def test_is_healthy_failure(self, adapter):
        """Test health check failure."""
        with patch.object(adapter._channel_manager, 'is_client_ready', side_effect=Exception("Health check failed")):
            result = await adapter.is_healthy()
            assert result is False

    def test_component_integration(self, adapter, mock_client, mock_tool_registry, mock_callback):
        """Test that all components are properly integrated."""
        # Test that setting up the adapter configures all components
        adapter = DiscordAdapter("test_token", mock_tool_registry, mock_client, mock_callback)
        
        # All handlers should have the client
        assert adapter._channel_manager.client == mock_client
        assert adapter._message_handler.client == mock_client
        assert adapter._guidance_handler.client == mock_client
        assert adapter._tool_handler.client == mock_client
        
        # Tool handler should have the registry
        assert adapter._tool_handler.tool_registry == mock_tool_registry
        
        # Channel manager should have the callback
        assert adapter._channel_manager.on_message_callback == mock_callback

    @pytest.mark.asyncio
    async def test_error_handling_propagation(self, adapter, mock_client):
        """Test that errors are properly handled and logged."""
        adapter._channel_manager.set_client(mock_client)
        
        # Test that RuntimeError from guidance handler is propagated
        with patch.object(adapter._guidance_handler, 'fetch_guidance_from_channel', 
                         side_effect=RuntimeError("Channel not found")):
            with patch('ciris_engine.config.config_manager.get_config') as mock_get_config:
                mock_config = MagicMock()
                mock_config.discord_deferral_channel_id = "123456"
                mock_get_config.return_value = mock_config
                
                with pytest.raises(RuntimeError):
                    await adapter.fetch_guidance({"task": "test"})

    def test_protocol_compliance(self, adapter):
        """Test that the adapter properly implements all required protocols."""
        # Check that adapter implements all three service protocols
        assert hasattr(adapter, 'send_message')
        assert hasattr(adapter, 'fetch_messages')
        assert hasattr(adapter, 'fetch_guidance')
        assert hasattr(adapter, 'send_deferral')
        assert hasattr(adapter, 'execute_tool')
        assert hasattr(adapter, 'get_available_tools')
        assert hasattr(adapter, 'get_tool_result')
        assert hasattr(adapter, 'validate_parameters')
        
        # Check Service base class methods
        assert hasattr(adapter, 'start')
        assert hasattr(adapter, 'stop')
        assert hasattr(adapter, 'is_healthy')
        assert hasattr(adapter, 'get_capabilities')