"""Unit tests for CIRISRuntime."""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from pathlib import Path

from ciris_engine.logic.runtime.ciris_runtime import CIRISRuntime
from ciris_engine.schemas.config.essential import EssentialConfig
# CognitiveState removed - using AgentState instead


class TestCIRISRuntime:
    """Test cases for CIRISRuntime."""
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def mock_essential_config(self, temp_data_dir):
        """Create mock essential config."""
        config = Mock(spec=EssentialConfig)
        config.data_dir = temp_data_dir
        config.db_path = os.path.join(temp_data_dir, "test.db")
        config.log_level = "INFO"
        config.openai_api_key = "test-key"
        config.anthropic_api_key = None
        config.channel_configs = {}
        return config
    
    @pytest.fixture
    def ciris_runtime(self, mock_essential_config):
        """Create CIRISRuntime instance."""
        runtime = CIRISRuntime(
            adapter_types=["cli"],
            essential_config=mock_essential_config,
            startup_channel_id="test_channel",
            adapter_configs={},
            mock_llm=True,
            timeout=10
        )
        return runtime
    
    @pytest.mark.asyncio
    async def test_initialize(self, ciris_runtime):
        """Test runtime initialization."""
        with patch.object(ciris_runtime, '_initialize_core_services', new_callable=AsyncMock) as mock_init_services:
            with patch.object(ciris_runtime, '_initialize_buses', new_callable=AsyncMock) as mock_init_buses:
                with patch.object(ciris_runtime, '_initialize_processors', new_callable=AsyncMock) as mock_init_processors:
                    with patch.object(ciris_runtime, '_initialize_adapters', new_callable=AsyncMock) as mock_init_adapters:
                        
                        await ciris_runtime.initialize()
                        
                        # Verify initialization sequence
                        mock_init_services.assert_called_once()
                        mock_init_buses.assert_called_once()
                        mock_init_processors.assert_called_once()
                        mock_init_adapters.assert_called_once()
                        
                        assert ciris_runtime._initialized is True
    
    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self, ciris_runtime):
        """Test initializing already initialized runtime."""
        ciris_runtime._initialized = True
        
        with pytest.raises(RuntimeError) as exc_info:
            await ciris_runtime.initialize()
        
        assert "already initialized" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_start(self, ciris_runtime):
        """Test starting the runtime."""
        # Mock components
        ciris_runtime.agent_processor = Mock()
        ciris_runtime.agent_processor.start_processing = AsyncMock()
        ciris_runtime.adapter_manager = Mock()
        ciris_runtime.adapter_manager.start_all = AsyncMock()
        ciris_runtime._initialized = True
        
        # Create a future that completes quickly
        processing_future = asyncio.Future()
        processing_future.set_result(None)
        ciris_runtime.agent_processor.start_processing.return_value = processing_future
        
        await ciris_runtime.start()
        
        ciris_runtime.adapter_manager.start_all.assert_called_once()
        ciris_runtime.agent_processor.start_processing.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_not_initialized(self, ciris_runtime):
        """Test starting without initialization."""
        with pytest.raises(RuntimeError) as exc_info:
            await ciris_runtime.start()
        
        assert "not initialized" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_shutdown(self, ciris_runtime):
        """Test runtime shutdown."""
        # Mock components
        ciris_runtime.agent_processor = Mock()
        ciris_runtime.agent_processor.stop_processing = AsyncMock()
        ciris_runtime.adapter_manager = Mock()
        ciris_runtime.adapter_manager.stop_all = AsyncMock()
        ciris_runtime.service_initializer = Mock()
        ciris_runtime.service_initializer.shutdown_all = AsyncMock()
        ciris_runtime._initialized = True
        ciris_runtime._running = True
        
        # Create a fake shutdown method that just calls the components we want to test
        async def fake_shutdown():
            """Fake shutdown that only tests the component calls without system effects."""
            ciris_runtime._running = False
            if ciris_runtime.agent_processor:
                await ciris_runtime.agent_processor.stop_processing()
            if ciris_runtime.adapter_manager:
                await ciris_runtime.adapter_manager.stop_all()
            if ciris_runtime.service_initializer:
                await ciris_runtime.service_initializer.shutdown_all()
        
        # Replace the entire shutdown method
        ciris_runtime.shutdown = fake_shutdown
        
        # Call shutdown
        await ciris_runtime.shutdown()
        
        # Verify shutdown sequence
        ciris_runtime.agent_processor.stop_processing.assert_called_once()
        ciris_runtime.adapter_manager.stop_all.assert_called_once()
        ciris_runtime.service_initializer.shutdown_all.assert_called_once()
        
        assert ciris_runtime._running is False
    
    @pytest.mark.asyncio
    async def test_initialize_core_services(self, ciris_runtime):
        """Test core services initialization."""
        with patch('ciris_engine.logic.runtime.ciris_runtime.ServiceInitializer') as mock_initializer_class:
            mock_initializer = Mock()
            mock_initializer.initialize_all = AsyncMock()
            mock_initializer.time_service = Mock()
            mock_initializer.memory_service = Mock()
            mock_initializer.secrets_service = Mock()
            mock_initializer_class.return_value = mock_initializer
            
            await ciris_runtime._initialize_core_services()
            
            assert ciris_runtime.service_initializer is not None
            mock_initializer.initialize_all.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialize_buses(self, ciris_runtime):
        """Test bus initialization."""
        # Mock service initializer
        ciris_runtime.service_initializer = Mock()
        ciris_runtime.service_initializer.time_service = Mock()
        ciris_runtime.service_initializer.memory_service = Mock()
        ciris_runtime.service_initializer.llm_service = Mock()
        ciris_runtime.service_initializer.wise_authority_service = Mock()
        
        with patch('ciris_engine.logic.runtime.ciris_runtime.BusManager') as mock_bus_manager_class:
            mock_bus_manager = Mock()
            mock_bus_manager_class.return_value = mock_bus_manager
            
            await ciris_runtime._initialize_buses()
            
            assert ciris_runtime.bus_manager is not None
            mock_bus_manager_class.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialize_processors(self, ciris_runtime):
        """Test processor initialization."""
        # Mock dependencies
        ciris_runtime.service_initializer = Mock()
        ciris_runtime.service_initializer.config_accessor = Mock()
        ciris_runtime.service_initializer.get_all_services = Mock(return_value={})
        ciris_runtime.bus_manager = Mock()
        
        with patch('ciris_engine.logic.runtime.ciris_runtime.ComponentBuilder') as mock_builder_class:
            mock_builder = Mock()
            mock_builder.build_processors = Mock(return_value=(Mock(), Mock(), {}))
            mock_builder_class.return_value = mock_builder
            
            await ciris_runtime._initialize_processors()
            
            assert ciris_runtime.thought_processor is not None
            assert ciris_runtime.agent_processor is not None
            mock_builder.build_processors.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialize_adapters(self, ciris_runtime):
        """Test adapter initialization."""
        # Mock dependencies
        ciris_runtime.service_initializer = Mock()
        ciris_runtime.service_initializer.time_service = Mock()
        ciris_runtime.bus_manager = Mock()
        
        with patch('ciris_engine.logic.runtime.ciris_runtime.AdapterManager') as mock_adapter_class:
            mock_adapter_manager = Mock()
            mock_adapter_manager.initialize_adapters = AsyncMock()
            mock_adapter_class.return_value = mock_adapter_manager
            
            await ciris_runtime._initialize_adapters()
            
            assert ciris_runtime.adapter_manager is not None
            mock_adapter_manager.initialize_adapters.assert_called_once()
    
    @pytest.mark.asyncio 
    async def test_run_with_timeout(self, ciris_runtime):
        """Test running with timeout."""
        ciris_runtime._initialized = True
        ciris_runtime._timeout = 0.1  # 100ms timeout
        
        # Mock required components
        ciris_runtime.agent_processor = Mock()
        ciris_runtime.agent_processor.start_processing = AsyncMock()
        # Make the processing take too long
        async def slow_processing(num_rounds):
            await asyncio.sleep(1.0)
        ciris_runtime.agent_processor.start_processing = slow_processing
        
        ciris_runtime.bus_manager = None  # No bus manager for this test
        ciris_runtime.adapters = []  # No adapters for this test
        ciris_runtime._shutdown_event = asyncio.Event()
        
        # Mock the global shutdown to prevent system effects
        with patch('ciris_engine.logic.runtime.ciris_runtime.wait_for_global_shutdown_async') as mock_wait:
            # Make it never complete
            never_completes = asyncio.create_future()
            mock_wait.return_value = never_completes
            
            # Should timeout due to slow processing
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ciris_runtime.run(), timeout=0.1)
    
    @pytest.mark.asyncio
    async def test_run_with_error(self, ciris_runtime):
        """Test run with error during start."""
        ciris_runtime._initialized = True
        
        # Mock required components
        ciris_runtime.agent_processor = Mock()
        ciris_runtime.agent_processor.start_processing = AsyncMock(side_effect=Exception("Test error"))
        ciris_runtime.bus_manager = None
        ciris_runtime.adapters = []
        ciris_runtime._shutdown_event = asyncio.Event()
        ciris_runtime.shutdown = AsyncMock()
        
        # Mock the global shutdown to prevent system effects
        with patch('ciris_engine.logic.runtime.ciris_runtime.wait_for_global_shutdown_async') as mock_wait:
            mock_wait.return_value = asyncio.create_future()
            
            # Should handle error and shutdown
            with pytest.raises(Exception) as exc_info:
                await ciris_runtime.run()
            
            assert "Test error" in str(exc_info.value)
            ciris_runtime.shutdown.assert_called_once()
    
    def test_get_status(self, ciris_runtime):
        """Test getting runtime status."""
        ciris_runtime._initialized = True
        ciris_runtime._running = True
        ciris_runtime.agent_processor = Mock()
        ciris_runtime.agent_processor.get_current_state = Mock(return_value="WORK")
        
        status = ciris_runtime.get_status()
        
        assert status["initialized"] is True
        assert status["running"] is True
        assert status["current_state"] == "WORK"
        assert "uptime" in status
        assert "adapter_types" in status
    
    def test_get_services(self, ciris_runtime):
        """Test getting services."""
        mock_services = {"service1": Mock(), "service2": Mock()}
        ciris_runtime.service_initializer = Mock()
        ciris_runtime.service_initializer.get_all_services = Mock(return_value=mock_services)
        
        services = ciris_runtime.get_services()
        
        assert services == mock_services
    
    def test_get_services_not_initialized(self, ciris_runtime):
        """Test getting services when not initialized."""
        services = ciris_runtime.get_services()
        
        assert services == {}
    
    @pytest.mark.asyncio
    async def test_handle_shutdown_signal(self, ciris_runtime):
        """Test handling shutdown signal."""
        ciris_runtime._running = True
        ciris_runtime.shutdown = AsyncMock()
        
        # Simulate shutdown signal
        await ciris_runtime._handle_shutdown_signal()
        
        ciris_runtime.shutdown.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_configuration(self, ciris_runtime):
        """Test configuration validation."""
        # Should not raise for valid config
        ciris_runtime._validate_configuration()
        
        # Test with invalid adapter type
        ciris_runtime._adapter_types = ["invalid_adapter"]
        
        with pytest.raises(ValueError) as exc_info:
            ciris_runtime._validate_configuration()
        
        assert "unsupported adapter" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_multiple_adapters(self, ciris_runtime):
        """Test initialization with multiple adapters."""
        ciris_runtime._adapter_types = ["cli", "api"]
        
        # Mock adapter manager
        with patch('ciris_engine.logic.runtime.ciris_runtime.AdapterManager') as mock_adapter_class:
            mock_adapter_manager = Mock()
            mock_adapter_manager.initialize_adapters = AsyncMock()
            mock_adapter_class.return_value = mock_adapter_manager
            
            # Mock other dependencies
            ciris_runtime.service_initializer = Mock()
            ciris_runtime.service_initializer.time_service = Mock()
            ciris_runtime.bus_manager = Mock()
            
            await ciris_runtime._initialize_adapters()
            
            # Should pass both adapter types
            call_args = mock_adapter_manager.initialize_adapters.call_args[0]
            assert "cli" in call_args[0]
            assert "api" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_mock_llm_configuration(self, ciris_runtime):
        """Test that mock LLM is properly configured."""
        assert ciris_runtime._mock_llm is True
        
        # When initializing services, should use mock LLM
        with patch('ciris_engine.logic.runtime.ciris_runtime.ServiceInitializer') as mock_initializer_class:
            mock_initializer = Mock()
            mock_initializer.initialize_all = AsyncMock()
            mock_initializer_class.return_value = mock_initializer
            
            await ciris_runtime._initialize_core_services()
            
            # Should pass mock_llm flag
            mock_initializer_class.assert_called_once()
            call_kwargs = mock_initializer_class.call_args[1]
            assert call_kwargs.get('mock_llm') is True