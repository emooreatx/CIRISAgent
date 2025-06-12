"""Unit tests for RuntimeControlService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from typing import Dict, Any

from ciris_engine.runtime.runtime_control import RuntimeControlService
from ciris_engine.runtime.adapter_manager import RuntimeAdapterManager
from ciris_engine.runtime.config_manager_service import ConfigManagerService
from ciris_engine.schemas.runtime_control_schemas import (
    ProcessorStatus, ProcessorControlResponse, AdapterOperationResponse,
    RuntimeStatusResponse, ConfigOperationResponse, ConfigScope
)


@pytest.fixture
def mock_runtime():
    """Create mock runtime."""
    runtime = MagicMock()
    runtime.service_registry = MagicMock()
    runtime.service_registry.get_provider_info.return_value = {
        "handlers": {},
        "global_services": {},
        "circuit_breaker_stats": {}
    }
    runtime.service_registry.reset_circuit_breakers = MagicMock()
    return runtime


@pytest.fixture
def mock_adapter_manager():
    """Create mock adapter manager."""
    manager = MagicMock(spec=RuntimeAdapterManager)
    manager.load_adapter = AsyncMock(return_value={"success": True, "adapter_id": "test"})
    manager.unload_adapter = AsyncMock(return_value={"success": True})
    manager.list_adapters = AsyncMock(return_value=[])
    manager.get_adapter_info = AsyncMock(return_value={})
    return manager


@pytest.fixture
def mock_config_manager():
    """Create mock configuration manager."""
    manager = MagicMock(spec=ConfigManagerService)
    manager.initialize = AsyncMock()
    manager.get_config_value = AsyncMock(return_value={})
    manager.list_profiles = AsyncMock(return_value=[])
    return manager


@pytest.fixture
def mock_telemetry_collector():
    """Create mock telemetry collector."""
    collector = MagicMock()
    collector.get_processor_state = MagicMock(return_value={
        "current_state": "WORK",
        "rounds_completed": 5
    })
    collector.single_step = AsyncMock(return_value={
        "thoughts_processed": 2,
        "round_completed": True,
        "execution_time_ms": 150
    })
    collector.pause_processing = AsyncMock(return_value={
        "paused": True,
        "state": "PAUSED"
    })
    collector.resume_processing = AsyncMock(return_value={
        "resumed": True,
        "state": "WORK"
    })
    return collector


@pytest.fixture
def runtime_control(mock_runtime, mock_adapter_manager, mock_config_manager, mock_telemetry_collector):
    """Create runtime control service with mocks."""
    return RuntimeControlService(
        runtime=mock_runtime,
        telemetry_collector=mock_telemetry_collector,
        adapter_manager=mock_adapter_manager,
        config_manager=mock_config_manager
    )


@pytest.mark.asyncio
class TestRuntimeControlService:
    """Test RuntimeControlService functionality."""
    
    async def test_initialization(self, runtime_control, mock_config_manager):
        """Test service initialization."""
        await runtime_control.initialize()
        mock_config_manager.initialize.assert_called_once()
    
    async def test_single_step_success(self, runtime_control, mock_telemetry_collector):
        """Test successful single step execution."""
        result = await runtime_control.single_step()
        
        assert isinstance(result, ProcessorControlResponse)
        assert result.success is True
        mock_telemetry_collector.single_step.assert_called_once()
    
    async def test_single_step_no_telemetry_collector(self, mock_runtime, mock_adapter_manager, mock_config_manager):
        """Test single step when telemetry collector not available."""
        # Create runtime control without telemetry collector
        runtime_control = RuntimeControlService(
            runtime=mock_runtime,
            telemetry_collector=None,
            adapter_manager=mock_adapter_manager,
            config_manager=mock_config_manager
        )
        
        result = await runtime_control.single_step()
        
        assert isinstance(result, ProcessorControlResponse)
        assert result.success is False
        assert "Telemetry collector not available" in result.error
    
    async def test_pause_processing_success(self, runtime_control, mock_telemetry_collector):
        """Test successful processing pause."""
        result = await runtime_control.pause_processing()
        
        assert isinstance(result, ProcessorControlResponse)
        assert result.success is True
        mock_telemetry_collector.pause_processing.assert_called_once()
    
    async def test_resume_processing_success(self, runtime_control, mock_telemetry_collector):
        """Test successful processing resume."""
        result = await runtime_control.resume_processing()
        
        assert isinstance(result, ProcessorControlResponse)
        assert result.success is True
        mock_telemetry_collector.resume_processing.assert_called_once()
    
    async def test_shutdown_runtime_success(self, runtime_control, mock_runtime):
        """Test successful runtime shutdown."""
        # Mock the global shutdown function instead of runtime.shutdown
        with patch('ciris_engine.utils.shutdown_manager.request_global_shutdown') as mock_shutdown:
            result = await runtime_control.shutdown_runtime("Test shutdown")
            
            assert isinstance(result, ProcessorControlResponse)
            assert result.success is True
            mock_shutdown.assert_called_once_with("Runtime control: Test shutdown")
    
    async def test_load_adapter_success(self, runtime_control, mock_adapter_manager):
        """Test successful adapter loading."""
        result = await runtime_control.load_adapter(
            adapter_type="discord",
            adapter_id="test_discord",
            config={"token": "test_token"},
            auto_start=True
        )
        
        assert isinstance(result, AdapterOperationResponse)
        assert result.success is True
        mock_adapter_manager.load_adapter.assert_called_once_with(
            "discord",
            "test_discord",
            {"token": "test_token"}
        )
    
    async def test_unload_adapter_success(self, runtime_control, mock_adapter_manager):
        """Test successful adapter unloading."""
        result = await runtime_control.unload_adapter("test_adapter", force=False)
        
        assert isinstance(result, AdapterOperationResponse)
        assert result.success is True
        mock_adapter_manager.unload_adapter.assert_called_once_with("test_adapter")
    
    async def test_list_adapters(self, runtime_control, mock_adapter_manager):
        """Test listing adapters."""
        mock_adapter_manager.list_adapters.return_value = [
            {"adapter_id": "test1", "mode": "discord"},
            {"adapter_id": "test2", "mode": "api"}
        ]
        
        result = await runtime_control.list_adapters()
        
        assert len(result) == 2
        assert result[0]["adapter_id"] == "test1"
        assert result[1]["adapter_id"] == "test2"
    
    async def test_get_adapter_info(self, runtime_control, mock_adapter_manager):
        """Test getting adapter info."""
        mock_adapter_manager.get_adapter_info.return_value = {
            "adapter_id": "test",
            "mode": "discord"
        }
        
        result = await runtime_control.get_adapter_info("test")
        
        assert result is not None
        assert result["adapter_id"] == "test"
        assert result["mode"] == "discord"
    
    async def test_get_config_success(self, runtime_control, mock_config_manager):
        """Test getting configuration."""
        mock_config_manager.get_config_value.return_value = {"test": "value"}
        
        result = await runtime_control.get_config("test.path", False)
        
        # get_config returns the raw dict from config manager, not wrapped in ConfigOperationResponse
        assert isinstance(result, dict)
        assert result == {"test": "value"}
    
    async def test_update_config_success(self, runtime_control, mock_config_manager):
        """Test updating configuration."""
        # Mock to return a ConfigOperationResponse object instead of just True
        mock_response = ConfigOperationResponse(
            success=True,
            operation="update_config",
            timestamp=datetime.now(timezone.utc),
            path="test.path"
        )
        mock_config_manager.update_config_value = AsyncMock(return_value=mock_response)
        
        result = await runtime_control.update_config(
            path="test.path",
            value="new_value",
            scope=ConfigScope.SESSION,
            validation_level="strict",
            reason="Test update"
        )
        
        assert isinstance(result, ConfigOperationResponse)
        assert result.success is True
    
    async def test_validate_config_success(self, runtime_control, mock_config_manager):
        """Test configuration validation."""
        from ciris_engine.schemas.runtime_control_schemas import ConfigValidationResponse
        mock_config_manager.validate_config = AsyncMock(return_value=ConfigValidationResponse(
            valid=True,
            errors=[]
        ))
        
        result = await runtime_control.validate_config(
            config_data={"test": "value"},
            config_path="test.path"
        )
        
        assert result.valid is True
        assert result.errors == []
    
    async def test_get_service_registry_info_success(self, runtime_control, mock_runtime):
        """Test getting service registry information."""
        mock_runtime.service_registry.get_provider_info.return_value = {
            "handlers": {"test_handler": {"llm": []}},
            "global_services": {"communication": []},
            "circuit_breaker_stats": {}
        }
        
        result = await runtime_control.get_service_registry_info("test_handler", "llm")
        
        assert "handlers" in result
        assert "global_services" in result
        assert "circuit_breaker_stats" in result
        mock_runtime.service_registry.get_provider_info.assert_called_once_with("test_handler", "llm")
    
    async def test_get_service_registry_info_no_registry(self, runtime_control):
        """Test getting service registry info when registry not available."""
        runtime_control.runtime.service_registry = None
        
        result = await runtime_control.get_service_registry_info()
        
        assert "error" in result
        assert "not available" in result["error"]
    
    async def test_reset_circuit_breakers_success(self, runtime_control, mock_runtime):
        """Test resetting circuit breakers."""
        result = await runtime_control.reset_circuit_breakers("llm")
        
        assert result["success"] is True
        mock_runtime.service_registry.reset_circuit_breakers.assert_called_once()
    
    async def test_reset_circuit_breakers_no_registry(self, runtime_control):
        """Test resetting circuit breakers when registry not available."""
        runtime_control.runtime.service_registry = None
        
        result = await runtime_control.reset_circuit_breakers()
        
        assert result["success"] is False
        assert "not available" in result["error"]
    
    async def test_get_service_health_status_success(self, runtime_control, mock_runtime):
        """Test getting service health status."""
        mock_runtime.service_registry.get_provider_info.return_value = {
            "handlers": {
                "test_handler": {
                    "llm": [
                        {
                            "name": "provider1",
                            "priority": "HIGH",
                            "priority_group": 0,
                            "strategy": "FALLBACK",
                            "circuit_breaker_state": "closed"
                        }
                    ]
                }
            },
            "global_services": {
                "communication": [
                    {
                        "name": "global_comm",
                        "priority": "NORMAL", 
                        "priority_group": 0,
                        "strategy": "ROUND_ROBIN",
                        "circuit_breaker_state": "open"
                    }
                ]
            }
        }
        
        result = await runtime_control.get_service_health_status()
        
        assert result["overall_health"] == "degraded"  # One service unhealthy
        assert result["total_services"] == 2
        assert result["healthy_services"] == 1
        assert result["unhealthy_services"] == 1
        assert "test_handler.llm.provider1" in result["services"]
        assert "global.communication.global_comm" in result["services"]
    
    async def test_get_service_health_status_no_registry(self, runtime_control):
        """Test getting service health when registry not available."""
        runtime_control.runtime.service_registry = None
        
        result = await runtime_control.get_service_health_status()
        
        assert "error" in result
        assert "not available" in result["error"]
    
    async def test_get_service_selection_explanation(self, runtime_control):
        """Test getting service selection explanation."""
        result = await runtime_control.get_service_selection_explanation()
        
        assert "service_selection_logic" in result
        assert "overview" in result["service_selection_logic"]
        assert "priority_groups" in result["service_selection_logic"]
        assert "priority_levels" in result["service_selection_logic"]
        assert "selection_strategies" in result["service_selection_logic"]
        assert "example_scenarios" in result
    
    async def test_update_service_priority_not_implemented(self, runtime_control):
        """Test that service priority updates return not implemented."""
        result = await runtime_control.update_service_priority(
            provider_name="test_provider",
            new_priority="HIGH",
            new_priority_group=1,
            new_strategy="ROUND_ROBIN"
        )
        
        assert result["success"] is False
        assert "not yet implemented" in result["error"]
    
    async def test_get_runtime_status_success(self, runtime_control, mock_adapter_manager):
        """Test getting runtime status."""
        mock_adapter_manager.list_adapters.return_value = [
            {"adapter_id": "test1", "is_running": True},
            {"adapter_id": "test2", "is_running": False}
        ]
        
        result = await runtime_control.get_runtime_status()
        
        assert isinstance(result, RuntimeStatusResponse)
        assert result.processor_status == ProcessorStatus.RUNNING
        assert len(result.loaded_adapters) == 2
        assert len(result.active_adapters) == 1
    
    async def test_get_runtime_snapshot_success(self, runtime_control, mock_config_manager):
        """Test getting runtime snapshot."""
        mock_config_manager.get_config_value.return_value = {"test": "config"}
        
        # Create proper mock profiles
        profile1 = MagicMock()
        profile1.name = "profile1"
        profile1.is_active = True
        
        profile2 = MagicMock()
        profile2.name = "profile2"
        profile2.is_active = False
        
        mock_config_manager.list_profiles.return_value = [profile1, profile2]
        
        result = await runtime_control.get_runtime_snapshot()
        
        assert result.processor_status == ProcessorStatus.RUNNING
        assert result.configuration == {"test": "config"}
        assert result.active_profile == "profile1"
        assert "profile1" in result.loaded_profiles
        assert "profile2" in result.loaded_profiles
    
    async def test_error_handling_with_exception(self, runtime_control):
        """Test error handling when exceptions occur."""
        runtime_control.runtime = None  # Force error
        runtime_control.telemetry_collector = None  # Force telemetry error
        
        result = await runtime_control.single_step()
        
        assert isinstance(result, ProcessorControlResponse)
        assert result.success is False
        assert result.error is not None


@pytest.mark.asyncio
class TestRuntimeControlEdgeCases:
    """Test edge cases and error conditions."""
    
    async def test_processor_operations_with_none_runtime(self):
        """Test processor operations when runtime is None."""
        control = RuntimeControlService(runtime=None)
        
        result = await control.single_step()
        assert result.success is False
        
        result = await control.pause_processing()
        assert result.success is False
        
        result = await control.resume_processing()
        assert result.success is False
    
    async def test_adapter_operations_with_none_manager(self, mock_runtime):
        """Test adapter operations when manager is None."""
        control = RuntimeControlService(runtime=mock_runtime, adapter_manager=None)
        
        result = await control.load_adapter("test", "test_id", {})
        assert result.success is False
        
        result = await control.unload_adapter("test_id")
        assert result.success is False
        
        adapters = await control.list_adapters()
        assert adapters == []
    
    async def test_config_operations_with_none_manager(self, mock_runtime):
        """Test config operations when manager is None."""
        control = RuntimeControlService(runtime=mock_runtime, config_manager=None)
        
        # These should use the default ConfigManagerService, but will fail without initialization
        result = await control.get_config()
        assert isinstance(result, dict)
        assert "error" in result
    
    async def test_event_recording_success(self, runtime_control):
        """Test internal event recording."""
        # This tests the private method indirectly
        await runtime_control._record_event("test", "action", True, {"result": "data"})
        
        # Check that event was recorded in history
        history = runtime_control.get_events_history(1)
        assert len(history) == 1
        assert history[0]["category"] == "test"
        assert history[0]["action"] == "action"
        assert history[0]["success"] is True
    
    async def test_event_recording_with_error(self, runtime_control):
        """Test event recording with error."""
        await runtime_control._record_event("test", "failed_action", False, error="Test error")
        
        history = runtime_control.get_events_history(1)
        assert len(history) == 1
        assert history[0]["success"] is False
        assert history[0]["error"] == "Test error"
    
    def test_events_history_limit(self, runtime_control):
        """Test that events history respects limit."""
        # Get empty history first
        history = runtime_control.get_events_history(10)
        assert len(history) == 0