"""
Tests for the API platform adapter.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from ciris_engine.adapters.api.adapter import ApiPlatform
from ciris_engine.adapters.api.config import APIAdapterConfig
from ciris_engine.schemas.foundational_schemas_v1 import ServiceType
from ciris_engine.registries.base import Priority


@pytest.fixture
def mock_runtime():
    """Mock CIRIS runtime."""
    runtime = Mock()
    runtime.agent_profile = None
    runtime.multi_service_sink = AsyncMock()
    runtime.service_registry = AsyncMock()
    runtime.adapter_manager = Mock()
    runtime.config_manager = Mock()
    return runtime


@pytest.fixture
def api_platform(mock_runtime):
    """Create API platform instance."""
    return ApiPlatform(mock_runtime, host="127.0.0.1", port=8001)


@pytest.mark.asyncio
class TestApiPlatform:
    """Test cases for API platform adapter."""

    def test_init_with_kwargs(self, mock_runtime):
        """Test initialization with kwargs."""
        platform = ApiPlatform(
            mock_runtime,
            host="0.0.0.0",
            port=9000
        )
        
        assert platform.config.host == "0.0.0.0"
        assert platform.config.port == 9000
        assert platform.runtime == mock_runtime

    def test_init_with_profile(self, mock_runtime):
        """Test initialization with agent profile."""
        # Create mock profile with API config
        mock_profile = Mock()
        mock_api_config = Mock()
        mock_api_config.dict.return_value = {
            "host": "192.168.1.100",
            "port": 8080
        }
        mock_profile.api_config = mock_api_config
        mock_runtime.template = mock_profile
        
        platform = ApiPlatform(mock_runtime, host="127.0.0.1", port=8004)
        
        assert platform.config.host == "192.168.1.100"
        assert platform.config.port == 8080

    @patch.dict('os.environ', {'CIRIS_API_HOST': '10.0.0.1', 'CIRIS_API_PORT': '7000'})
    def test_init_with_env_vars(self, mock_runtime):
        """Test initialization with environment variables."""
        platform = ApiPlatform(mock_runtime, host="127.0.0.1", port=8005)
        
        # Environment variables should override defaults
        assert platform.config.host == "10.0.0.1"
        assert platform.config.port == 7000

    def test_services_registration(self, api_platform):
        """Test service registration."""
        registrations = api_platform.get_services_to_register()
        
        assert len(registrations) == 1
        
        reg = registrations[0]
        assert reg.service_type == ServiceType.COMMUNICATION
        assert reg.priority == Priority.NORMAL
        assert "SpeakHandler" in reg.handlers

    async def test_start(self, api_platform):
        """Test platform start."""
        with patch.object(api_platform.api_adapter, 'start') as mock_start:
            await api_platform.start()
            mock_start.assert_called_once()

    async def test_stop(self, api_platform):
        """Test platform stop."""
        with patch.object(api_platform.api_adapter, 'stop') as mock_stop:
            await api_platform.stop()
            mock_stop.assert_called_once()

    async def test_run_lifecycle(self, api_platform):
        """Test lifecycle management."""
        # Create a simple agent task
        async def dummy_agent_task():
            await asyncio.sleep(0.1)
            return "completed"
        
        agent_task = asyncio.create_task(dummy_agent_task())
        
        # Run lifecycle
        await api_platform.run_lifecycle(agent_task)
        
        # Task should complete
        assert agent_task.done()
        assert agent_task.result() == "completed"

    async def test_run_lifecycle_with_stop_event(self, api_platform):
        """Test lifecycle with stop event."""
        # Create a long-running agent task
        async def long_agent_task():
            await asyncio.sleep(10)
            return "completed"
        
        agent_task = asyncio.create_task(long_agent_task())
        
        # Start lifecycle in background
        lifecycle_task = asyncio.create_task(api_platform.run_lifecycle(agent_task))
        
        # Give it a moment to start
        await asyncio.sleep(0.1)
        
        # Stop the platform
        await api_platform.stop()
        
        # Lifecycle should complete quickly
        await asyncio.wait_for(lifecycle_task, timeout=1.0)
        
        # Agent task should be cancelled
        assert agent_task.cancelled()

    async def test_ensure_stop_event(self, api_platform):
        """Test stop event creation."""
        # Initially no stop event
        assert api_platform._web_server_stopped_event is None
        
        # Call ensure_stop_event
        api_platform._ensure_stop_event()
        
        # Should create event
        assert api_platform._web_server_stopped_event is not None
        assert isinstance(api_platform._web_server_stopped_event, asyncio.Event)  # type: ignore[unreachable]

    def test_ensure_stop_event_outside_loop(self, api_platform):
        """Test stop event creation outside async context."""
        # Simulate being outside event loop
        with patch('asyncio.Event', side_effect=RuntimeError("No event loop")):
            api_platform._ensure_stop_event()
            
            # Should handle gracefully
            assert api_platform._web_server_stopped_event is None

    async def test_telemetry_collector_integration(self, api_platform):
        """Test telemetry collector integration."""
        assert api_platform.telemetry_collector is not None
        assert api_platform.api_adapter.telemetry_collector is not None

    async def test_runtime_control_integration(self, api_platform):
        """Test runtime control integration."""
        assert api_platform.runtime_control_service is not None
        assert api_platform.api_adapter.runtime_control is not None

    async def test_api_adapter_capabilities(self, api_platform):
        """Test API adapter capabilities."""
        capabilities = await api_platform.api_adapter.get_capabilities()
        
        # Should have basic capabilities
        assert "send_message" in capabilities
        assert "fetch_messages" in capabilities
        assert "health_check" in capabilities
        
        # Should have runtime and telemetry capabilities
        assert "runtime_status" in capabilities
        assert "metrics" in capabilities


@pytest.mark.asyncio
class TestApiPlatformIntegration:
    """Integration tests for API platform."""

    async def test_full_lifecycle(self, mock_runtime):
        """Test complete platform lifecycle."""
        platform = ApiPlatform(mock_runtime, host="127.0.0.1", port=8002)
        
        # Test start
        await platform.start()
        
        # Test service registration
        registrations = platform.get_services_to_register()
        assert len(registrations) > 0
        
        # Test capabilities
        capabilities = await platform.api_adapter.get_capabilities()
        assert len(capabilities) > 0
        
        # Test stop
        await platform.stop()

    async def test_configuration_cascade(self, mock_runtime):
        """Test configuration cascading from profile to env vars."""
        # Setup profile config
        mock_profile = Mock()
        mock_api_config = Mock()
        mock_api_config.dict.return_value = {
            "host": "profile_host",
            "port": 7777
        }
        mock_profile.api_config = mock_api_config
        mock_runtime.template = mock_profile
        
        # Setup environment override
        with patch.dict('os.environ', {'CIRIS_API_PORT': '8888'}):
            platform = ApiPlatform(mock_runtime, host="127.0.0.1", port=8006)
            
            # Host should come from profile
            assert platform.config.host == "profile_host"
            # Port should be overridden by environment
            assert platform.config.port == 8888

    async def test_service_dependency_injection(self, mock_runtime):
        """Test that services are properly injected into API adapter."""
        platform = ApiPlatform(mock_runtime, host="127.0.0.1", port=8007)
        
        # Verify dependencies are passed to API adapter
        assert platform.api_adapter.multi_service_sink == mock_runtime.multi_service_sink
        assert platform.api_adapter.service_registry == mock_runtime.service_registry
        assert platform.api_adapter.runtime_control is not None
        assert platform.api_adapter.telemetry_collector is not None

    async def test_error_handling_during_start(self, mock_runtime):
        """Test error handling during platform start."""
        platform = ApiPlatform(mock_runtime, host="127.0.0.1", port=8008)
        
        # Mock API adapter start to fail
        with patch.object(platform.api_adapter, 'start', side_effect=Exception("Start failed")):
            with pytest.raises(Exception, match="Start failed"):
                await platform.start()

    async def test_error_handling_during_stop(self, mock_runtime):
        """Test error handling during platform stop."""
        platform = ApiPlatform(mock_runtime, host="127.0.0.1", port=8003)
        
        # Start first
        await platform.start()
        
        # Mock API adapter stop to fail
        with patch.object(platform.api_adapter, 'stop', side_effect=Exception("Stop failed")):
            with pytest.raises(Exception, match="Stop failed"):
                await platform.stop()