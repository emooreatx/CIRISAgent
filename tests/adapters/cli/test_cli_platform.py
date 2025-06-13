"""
Tests for the CLI platform adapter.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from ciris_engine.adapters.cli.adapter import CliPlatform
from ciris_engine.adapters.cli.config import CLIAdapterConfig
from ciris_engine.schemas.foundational_schemas_v1 import ServiceType, IncomingMessage
from ciris_engine.registries.base import Priority


@pytest.fixture
def mock_runtime():
    """Mock CIRIS runtime."""
    runtime = Mock()
    runtime.agent_profile = None
    runtime.multi_service_sink = AsyncMock()
    runtime.service_registry = AsyncMock()
    runtime.memory_service = Mock()
    runtime.agent_id = "test_agent"
    return runtime


@pytest.fixture
def cli_platform_non_interactive(mock_runtime):
    """Create CLI platform instance in non-interactive mode."""
    return CliPlatform(mock_runtime, interactive=False)


@pytest.fixture
def cli_platform_interactive(mock_runtime):
    """Create CLI platform instance in interactive mode."""
    return CliPlatform(mock_runtime, interactive=True)


@pytest.mark.asyncio
class TestCliPlatform:
    """Test cases for CLI platform adapter."""

    def test_init_with_kwargs(self, mock_runtime):
        """Test initialization with kwargs."""
        platform = CliPlatform(mock_runtime, interactive=True)
        
        assert platform.config.interactive is True
        assert platform.runtime == mock_runtime

    def test_init_with_provided_config(self, mock_runtime):
        """Test initialization with provided config."""
        config = CLIAdapterConfig()
        config.interactive = False
        
        platform = CliPlatform(mock_runtime, adapter_config=config)
        
        assert platform.config == config
        assert platform.config.interactive is False

    def test_init_with_profile(self, mock_runtime):
        """Test initialization with agent profile."""
        # Create mock profile with CLI config
        mock_profile = Mock()
        mock_cli_config = Mock()
        mock_cli_config.dict.return_value = {
            "interactive": True
        }
        mock_profile.cli_config = mock_cli_config
        mock_runtime.agent_profile = mock_profile
        
        platform = CliPlatform(mock_runtime)
        
        assert platform.config.interactive is True

    @patch.dict('os.environ', {'CIRIS_CLI_INTERACTIVE': 'false'})
    def test_init_with_env_vars(self, mock_runtime):
        """Test initialization with environment variables."""
        platform = CliPlatform(mock_runtime)
        
        # Environment variables should override defaults
        assert platform.config.interactive is False

    def test_services_registration(self, cli_platform_non_interactive):
        """Test service registration."""
        registrations = cli_platform_non_interactive.get_services_to_register()
        
        assert len(registrations) == 3
        
        # Check service types
        service_types = [reg.service_type for reg in registrations]
        assert ServiceType.COMMUNICATION in service_types
        assert ServiceType.TOOL in service_types
        assert ServiceType.WISE_AUTHORITY in service_types
        
        # Check handlers
        comm_reg = next(reg for reg in registrations if reg.service_type == ServiceType.COMMUNICATION)
        assert "SpeakHandler" in comm_reg.handlers
        assert "ObserveHandler" in comm_reg.handlers

    async def test_handle_incoming_message(self, cli_platform_non_interactive):
        """Test handling incoming messages."""
        msg = IncomingMessage(
            message_id="test_msg",
            author_id="user123",
            author_name="Test User",
            content="Hello CIRIS",
            destination_id="cli"
        )
        
        await cli_platform_non_interactive._handle_incoming_message(msg)
        
        # Verify message was sent to multi-service sink
        mock_runtime = cli_platform_non_interactive.runtime
        mock_runtime.multi_service_sink.observe_message.assert_called_once_with(
            "ObserveHandler", msg, {"source": "cli"}
        )

    async def test_handle_incoming_message_no_sink(self, mock_runtime):
        """Test handling messages without multi-service sink."""
        mock_runtime.multi_service_sink = None
        platform = CliPlatform(mock_runtime, interactive=False)
        
        msg = IncomingMessage(
            message_id="test_msg",
            author_id="user123", 
            author_name="Test User",
            content="Hello CIRIS",
            destination_id="cli"
        )
        
        # Should handle gracefully without sink
        await platform._handle_incoming_message(msg)

    async def test_handle_incoming_message_exception(self, cli_platform_non_interactive):
        """Test handling messages with sink exception."""
        msg = IncomingMessage(
            message_id="test_msg",
            author_id="user123",
            author_name="Test User", 
            content="Hello CIRIS",
            destination_id="cli"
        )
        
        # Mock sink to raise exception
        mock_runtime = cli_platform_non_interactive.runtime
        mock_runtime.multi_service_sink.observe_message.side_effect = Exception("Sink error")
        
        # Should handle exception gracefully
        await cli_platform_non_interactive._handle_incoming_message(msg)

    async def test_start_non_interactive(self, cli_platform_non_interactive):
        """Test starting non-interactive platform."""
        with patch.object(cli_platform_non_interactive.cli_adapter, 'start') as mock_start:
            await cli_platform_non_interactive.start()
            mock_start.assert_called_once()

    async def test_start_interactive(self, cli_platform_interactive):
        """Test starting interactive platform."""
        with patch.object(cli_platform_interactive.cli_adapter, 'start') as mock_start:
            await cli_platform_interactive.start()
            mock_start.assert_called_once()

    async def test_stop_non_interactive(self, cli_platform_non_interactive):
        """Test stopping non-interactive platform."""
        with patch.object(cli_platform_non_interactive.cli_adapter, 'stop') as mock_stop:
            await cli_platform_non_interactive.stop()
            mock_stop.assert_called_once()

    async def test_stop_interactive(self, cli_platform_interactive):
        """Test stopping interactive platform."""
        with patch.object(cli_platform_interactive.cli_adapter, 'stop') as mock_stop:
            await cli_platform_interactive.stop()
            mock_stop.assert_called_once()

    async def test_run_lifecycle_success(self, cli_platform_non_interactive):
        """Test successful lifecycle run."""
        async def dummy_agent_task():
            await asyncio.sleep(0.1)
            return "completed"
        
        agent_task = asyncio.create_task(dummy_agent_task())
        
        await cli_platform_non_interactive.run_lifecycle(agent_task)
        
        assert agent_task.done()
        assert agent_task.result() == "completed"

    async def test_run_lifecycle_cancelled(self, cli_platform_non_interactive):
        """Test lifecycle with cancelled task."""
        async def dummy_agent_task():
            await asyncio.sleep(10)
            return "completed"
        
        agent_task = asyncio.create_task(dummy_agent_task())
        
        # Cancel the task immediately
        agent_task.cancel()
        
        # Should handle cancellation gracefully
        await cli_platform_non_interactive.run_lifecycle(agent_task)
        
        assert agent_task.cancelled()

    async def test_run_lifecycle_exception(self, cli_platform_non_interactive):
        """Test lifecycle with task exception."""
        async def failing_agent_task():
            raise Exception("Agent task failed")
        
        agent_task = asyncio.create_task(failing_agent_task())
        
        # Should handle exception gracefully
        await cli_platform_non_interactive.run_lifecycle(agent_task)
        
        assert agent_task.done()
        assert agent_task.exception() is not None

    async def test_cli_adapter_dependency_injection(self, cli_platform_non_interactive):
        """Test that CLI adapter gets proper dependencies."""
        adapter = cli_platform_non_interactive.cli_adapter
        
        assert adapter.interactive == cli_platform_non_interactive.config.interactive
        assert adapter.multi_service_sink == cli_platform_non_interactive.runtime.multi_service_sink
        assert adapter.on_message == cli_platform_non_interactive._handle_incoming_message

    async def test_cli_adapter_capabilities(self, cli_platform_non_interactive):
        """Test CLI adapter capabilities."""
        capabilities = await cli_platform_non_interactive.cli_adapter.get_capabilities()
        
        # Should have basic capabilities
        assert "send_message" in capabilities
        assert "fetch_messages" in capabilities
        assert "fetch_guidance" in capabilities
        assert "send_deferral" in capabilities
        assert "execute_tool" in capabilities


@pytest.mark.asyncio
class TestCliPlatformIntegration:
    """Integration tests for CLI platform."""

    async def test_full_lifecycle_non_interactive(self, mock_runtime):
        """Test complete non-interactive platform lifecycle."""
        platform = CliPlatform(mock_runtime, interactive=False)
        
        # Test start
        await platform.start()
        
        # Test service registration
        registrations = platform.get_services_to_register()
        assert len(registrations) == 3
        
        # Test capabilities
        capabilities = await platform.cli_adapter.get_capabilities()
        assert len(capabilities) > 0
        assert "interactive_mode" not in capabilities
        
        # Test stop
        await platform.stop()

    async def test_full_lifecycle_interactive(self, mock_runtime):
        """Test complete interactive platform lifecycle."""
        platform = CliPlatform(mock_runtime, interactive=True)
        
        # Test start
        await platform.start()
        
        # Test service registration
        registrations = platform.get_services_to_register()
        assert len(registrations) == 3
        
        # Test capabilities
        capabilities = await platform.cli_adapter.get_capabilities()
        assert len(capabilities) > 0
        assert "interactive_mode" in capabilities
        
        # Test stop
        await platform.stop()

    async def test_message_flow_integration(self, cli_platform_interactive):
        """Test complete message flow."""
        # Create a test message
        test_msg = IncomingMessage(
            message_id="integration_test",
            author_id="test_user",
            author_name="Test User",
            content="Integration test message",
            destination_id="cli"
        )
        
        # Handle the message
        await cli_platform_interactive._handle_incoming_message(test_msg)
        
        # Verify it was sent to sink
        mock_runtime = cli_platform_interactive.runtime
        mock_runtime.multi_service_sink.observe_message.assert_called_once_with(
            "ObserveHandler", test_msg, {"source": "cli"}
        )

    async def test_configuration_cascade(self, mock_runtime):
        """Test configuration cascading from profile to env vars."""
        # Setup profile config
        mock_profile = Mock()
        mock_cli_config = Mock()
        mock_cli_config.dict.return_value = {
            "interactive": True
        }
        mock_profile.cli_config = mock_cli_config
        mock_runtime.agent_profile = mock_profile
        
        # Setup environment override
        with patch.dict('os.environ', {'CIRIS_CLI_INTERACTIVE': 'false'}):
            platform = CliPlatform(mock_runtime)
            
            # Environment should override profile
            assert platform.config.interactive is False

    async def test_service_provider_consistency(self, cli_platform_non_interactive):
        """Test that all registrations use the same adapter instance."""
        registrations = cli_platform_non_interactive.get_services_to_register()
        
        # All registrations should use the same provider instance
        providers = [reg.provider for reg in registrations]
        unique_providers = set(id(provider) for provider in providers)
        
        assert len(unique_providers) == 1
        assert providers[0] == cli_platform_non_interactive.cli_adapter

    async def test_concurrent_message_handling(self, cli_platform_non_interactive):
        """Test concurrent message handling."""
        messages = []
        for i in range(10):
            msg = IncomingMessage(
                message_id=f"msg_{i}",
                author_id="user123",
                author_name="Test User",
                content=f"Message {i}",
                destination_id="cli"
            )
            messages.append(msg)
        
        # Handle all messages concurrently
        tasks = [
            cli_platform_non_interactive._handle_incoming_message(msg)
            for msg in messages
        ]
        
        await asyncio.gather(*tasks)
        
        # Verify all were handled
        mock_runtime = cli_platform_non_interactive.runtime
        assert mock_runtime.multi_service_sink.observe_message.call_count == 10

    async def test_error_recovery(self, cli_platform_non_interactive):
        """Test error recovery in message handling."""
        mock_runtime = cli_platform_non_interactive.runtime
        
        # First message fails
        mock_runtime.multi_service_sink.observe_message.side_effect = Exception("First error")
        
        msg1 = IncomingMessage(
            message_id="msg1",
            author_id="user123",
            author_name="Test User",
            content="First message",
            destination_id="cli"
        )
        
        await cli_platform_non_interactive._handle_incoming_message(msg1)
        
        # Reset mock to succeed
        mock_runtime.multi_service_sink.observe_message.side_effect = None
        
        msg2 = IncomingMessage(
            message_id="msg2", 
            author_id="user123",
            author_name="Test User",
            content="Second message",
            destination_id="cli"
        )
        
        await cli_platform_non_interactive._handle_incoming_message(msg2)
        
        # Should have tried both messages
        assert mock_runtime.multi_service_sink.observe_message.call_count == 2

    async def test_adapter_service_integration(self, cli_platform_non_interactive):
        """Test integration between platform and adapter services."""
        adapter = cli_platform_non_interactive.cli_adapter
        
        # Test communication service
        with patch('builtins.print'), patch('ciris_engine.persistence.add_correlation'):
            result = await adapter.send_message("test", "Hello World")
            assert result is True
        
        # Test tool service
        with patch('os.listdir', return_value=['file.txt']), \
             patch('ciris_engine.persistence.add_correlation'):
            result = await adapter.execute_tool("list_files", {"path": "/test"})
            assert result["success"] is True
        
        # Test wise authority service
        with patch('builtins.print'), patch('ciris_engine.persistence.add_correlation'):
            result = await adapter.send_deferral("thought_123", "Complex decision")
            assert result is True