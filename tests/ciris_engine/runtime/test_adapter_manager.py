"""Unit tests for RuntimeAdapterManager."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from typing import Dict, Any

from ciris_engine.runtime.adapter_manager import RuntimeAdapterManager, AdapterInstance
from ciris_engine.protocols.adapter_interface import PlatformAdapter, ServiceRegistration
from ciris_engine.schemas.foundational_schemas_v1 import ServiceType
from ciris_engine.registries.base import Priority, SelectionStrategy


class MockAdapter:
    """Mock adapter for testing."""
    
    def __init__(self, runtime, **kwargs):
        self.runtime = runtime
        self.config = kwargs
        self.is_started = False
        
    async def start(self) -> None:
        self.is_started = True
        
    async def stop(self) -> None:
        self.is_started = False
        
    def get_services_to_register(self) -> list[ServiceRegistration]:
        return [
            ServiceRegistration(
                service_type=ServiceType.COMMUNICATION,
                provider=self,
                priority=Priority.NORMAL,
                handlers=["test_handler"],
                capabilities=["test_capability"],
                priority_group=0,
                strategy=SelectionStrategy.FALLBACK
            )
        ]


class MockRuntime:
    """Mock runtime for testing."""
    
    def __init__(self):
        self.adapters: list = []
        self.service_registry = MagicMock()


@pytest.fixture
def mock_runtime():
    """Create mock runtime."""
    return MockRuntime()


@pytest.fixture
def adapter_manager(mock_runtime):
    """Create adapter manager with mock runtime."""
    return RuntimeAdapterManager(mock_runtime)


@pytest.mark.asyncio
class TestRuntimeAdapterManager:
    """Test RuntimeAdapterManager functionality."""
    
    async def test_load_adapter_success(self, adapter_manager, mock_runtime):
        """Test successful adapter loading."""
        with patch('ciris_engine.runtime.adapter_manager.load_adapter', return_value=MockAdapter):
            result = await adapter_manager.load_adapter(
                mode="test",
                adapter_id="test_adapter",
                config_params={"param1": "value1"}
            )
            
        assert result["success"] is True
        assert result["adapter_id"] == "test_adapter"
        assert result["mode"] == "test"
        assert "test_adapter" in adapter_manager.loaded_adapters
        assert len(mock_runtime.adapters) == 1
        
        # Check adapter instance properties
        instance = adapter_manager.loaded_adapters["test_adapter"]
        assert instance.adapter_id == "test_adapter"
        assert instance.mode == "test"
        assert instance.is_running is True
        assert instance.config_params == {"param1": "value1"}
        assert isinstance(instance.loaded_at, datetime)
    
    async def test_load_adapter_auto_id_generation(self, adapter_manager):
        """Test automatic adapter ID generation."""
        with patch('ciris_engine.runtime.adapter_manager.load_adapter', return_value=MockAdapter):
            result1 = await adapter_manager.load_adapter(mode="test")
            result2 = await adapter_manager.load_adapter(mode="test")
            
        assert result1["adapter_id"] == "test_1"
        assert result2["adapter_id"] == "test_2"
    
    async def test_load_adapter_duplicate_id(self, adapter_manager):
        """Test loading adapter with duplicate ID fails."""
        with patch('ciris_engine.runtime.adapter_manager.load_adapter', return_value=MockAdapter):
            await adapter_manager.load_adapter(mode="test", adapter_id="duplicate")
            result = await adapter_manager.load_adapter(mode="test", adapter_id="duplicate")
            
        assert result["success"] is False
        assert "already exists" in result["error"]
    
    async def test_load_adapter_failure(self, adapter_manager):
        """Test adapter loading failure handling."""
        with patch('ciris_engine.runtime.adapter_manager.load_adapter', side_effect=Exception("Load failed")):
            result = await adapter_manager.load_adapter(mode="test")
            
        assert result["success"] is False
        assert "Load failed" in result["error"]
    
    async def test_unload_adapter_success(self, adapter_manager, mock_runtime):
        """Test successful adapter unloading."""
        # First load an adapter
        with patch('ciris_engine.runtime.adapter_manager.load_adapter', return_value=MockAdapter):
            await adapter_manager.load_adapter(mode="discord", adapter_id="discord1")
            await adapter_manager.load_adapter(mode="api", adapter_id="api1")
            
        # Then unload one
        result = await adapter_manager.unload_adapter("discord1")
        
        assert result["success"] is True
        assert result["adapter_id"] == "discord1"
        assert "discord1" not in adapter_manager.loaded_adapters
        assert "api1" in adapter_manager.loaded_adapters  # Other adapter remains
    
    async def test_unload_adapter_not_found(self, adapter_manager):
        """Test unloading non-existent adapter."""
        result = await adapter_manager.unload_adapter("nonexistent")
        
        assert result["success"] is False
        assert "not found" in result["error"]
    
    async def test_unload_last_communication_adapter_blocked(self, adapter_manager):
        """Test that unloading last communication adapter is blocked."""
        # Load only one communication adapter
        with patch('ciris_engine.runtime.adapter_manager.load_adapter', return_value=MockAdapter):
            await adapter_manager.load_adapter(mode="discord", adapter_id="last_comm")
            
        result = await adapter_manager.unload_adapter("last_comm")
        
        assert result["success"] is False
        assert "communication-capable adapters" in result["error"]
        assert "last_comm" in adapter_manager.loaded_adapters  # Should remain loaded
    
    async def test_unload_adapter_with_multiple_comm_adapters(self, adapter_manager):
        """Test unloading communication adapter when others exist."""
        with patch('ciris_engine.runtime.adapter_manager.load_adapter', return_value=MockAdapter):
            await adapter_manager.load_adapter(mode="discord", adapter_id="discord1")
            await adapter_manager.load_adapter(mode="api", adapter_id="api1")
            
        result = await adapter_manager.unload_adapter("discord1")
        
        assert result["success"] is True
        assert "discord1" not in adapter_manager.loaded_adapters
        assert "api1" in adapter_manager.loaded_adapters
    
    async def test_reload_adapter_success(self, adapter_manager):
        """Test successful adapter reloading."""
        # Load initial adapter
        with patch('ciris_engine.runtime.adapter_manager.load_adapter', return_value=MockAdapter):
            await adapter_manager.load_adapter(
                mode="test", 
                adapter_id="reload_test",
                config_params={"param1": "old_value"}
            )
            
            # Reload with new config
            result = await adapter_manager.reload_adapter(
                "reload_test",
                config_params={"param1": "new_value"}
            )
            
        assert result["success"] is True
        assert result["adapter_id"] == "reload_test"
        
        # Check new configuration
        instance = adapter_manager.loaded_adapters["reload_test"]
        assert instance.config_params == {"param1": "new_value"}
    
    async def test_reload_adapter_not_found(self, adapter_manager):
        """Test reloading non-existent adapter."""
        result = await adapter_manager.reload_adapter("nonexistent")
        
        assert result["success"] is False
        assert "not found" in result["error"]
    
    async def test_list_adapters(self, adapter_manager):
        """Test listing loaded adapters."""
        with patch('ciris_engine.runtime.adapter_manager.load_adapter', return_value=MockAdapter):
            await adapter_manager.load_adapter(mode="test1", adapter_id="adapter1")
            await adapter_manager.load_adapter(mode="test2", adapter_id="adapter2")
            
        adapters = await adapter_manager.list_adapters()
        
        assert len(adapters) == 2
        adapter_ids = [a["adapter_id"] for a in adapters]
        assert "adapter1" in adapter_ids
        assert "adapter2" in adapter_ids
        
        # Check adapter info structure
        adapter_info = adapters[0]
        assert "adapter_id" in adapter_info
        assert "mode" in adapter_info
        assert "is_running" in adapter_info
        assert "health_status" in adapter_info
        assert "services_count" in adapter_info
        assert "loaded_at" in adapter_info
    
    async def test_get_adapter_status_success(self, adapter_manager):
        """Test getting adapter status."""
        with patch('ciris_engine.runtime.adapter_manager.load_adapter', return_value=MockAdapter):
            await adapter_manager.load_adapter(mode="test", adapter_id="status_test")
            
        status = await adapter_manager.get_adapter_status("status_test")
        
        assert status["success"] is True
        assert status["adapter_id"] == "status_test"
        assert status["mode"] == "test"
        assert status["is_running"] is True
        assert "health_status" in status
        assert "loaded_at" in status
        assert "uptime_seconds" in status
        assert "service_details" in status
    
    async def test_get_adapter_status_not_found(self, adapter_manager):
        """Test getting status of non-existent adapter."""
        status = await adapter_manager.get_adapter_status("nonexistent")
        
        assert status["success"] is False
        assert "not found" in status["error"]
    
    async def test_get_adapter_info(self, adapter_manager):
        """Test getting adapter info."""
        with patch('ciris_engine.runtime.adapter_manager.load_adapter', return_value=MockAdapter):
            await adapter_manager.load_adapter(
                mode="test",
                adapter_id="info_test",
                config_params={"test": "value"}
            )
            
        info = await adapter_manager.get_adapter_info("info_test")
        
        assert info["adapter_id"] == "info_test"
        assert info["mode"] == "test"
        assert info["config"] == {"test": "value"}
        assert "load_time" in info
        assert info["is_running"] is True
    
    async def test_get_adapter_info_not_found(self, adapter_manager):
        """Test getting info of non-existent adapter."""
        info = await adapter_manager.get_adapter_info("nonexistent")
        assert info == {}
    
    def test_get_communication_adapter_status(self, adapter_manager):
        """Test getting communication adapter status."""
        # Create mock instances
        discord_instance = MagicMock()
        discord_instance.mode = "discord"
        discord_instance.is_running = True
        
        api_instance = MagicMock()
        api_instance.mode = "api" 
        api_instance.is_running = True
        
        tool_instance = MagicMock()
        tool_instance.mode = "tool"
        tool_instance.is_running = True
        
        adapter_manager.loaded_adapters = {
            "discord1": discord_instance,
            "api1": api_instance,
            "tool1": tool_instance
        }
        
        status = adapter_manager.get_communication_adapter_status()
        
        assert status["total_communication_adapters"] == 2  # discord and api only
        assert status["running_communication_adapters"] == 2
        assert status["safe_to_unload"] is True
        assert status["warning_message"] is None
        
        # Check that only communication adapters are included
        comm_adapters = status["communication_adapters"]
        assert len(comm_adapters) == 2
        modes = [adapter["mode"] for adapter in comm_adapters]
        assert "discord" in modes
        assert "api" in modes
        assert "tool" not in modes
    
    def test_get_communication_adapter_status_unsafe(self, adapter_manager):
        """Test communication adapter status when only one running."""
        discord_instance = MagicMock()
        discord_instance.mode = "discord"
        discord_instance.is_running = True
        
        adapter_manager.loaded_adapters = {"discord1": discord_instance}
        
        status = adapter_manager.get_communication_adapter_status()
        
        assert status["total_communication_adapters"] == 1
        assert status["running_communication_adapters"] == 1
        assert status["safe_to_unload"] is False
        assert "Only one communication adapter remaining" in status["warning_message"]
    
    async def test_service_registration(self, adapter_manager, mock_runtime):
        """Test that services are properly registered."""
        with patch('ciris_engine.runtime.adapter_manager.load_adapter', return_value=MockAdapter):
            await adapter_manager.load_adapter(mode="test", adapter_id="service_test")
            
        # Check that service registry register was called
        assert mock_runtime.service_registry.register.called
        
        # Check call arguments
        call_args = mock_runtime.service_registry.register.call_args
        assert call_args[1]["handler"] == "test_handler"
        assert call_args[1]["service_type"] == "communication"
        assert call_args[1]["priority"] == Priority.NORMAL
        assert call_args[1]["capabilities"] == ["test_capability"]
        assert call_args[1]["priority_group"] == 0
        assert call_args[1]["strategy"] == SelectionStrategy.FALLBACK


@pytest.mark.asyncio
class TestAdapterInstance:
    """Test AdapterInstance dataclass."""
    
    def test_adapter_instance_creation(self):
        """Test creating adapter instance."""
        mock_adapter = MagicMock()
        now = datetime.now(timezone.utc)
        
        instance = AdapterInstance(
            adapter_id="test_id",
            mode="test_mode", 
            adapter=mock_adapter,
            config_params={"test": "value"},
            loaded_at=now
        )
        
        assert instance.adapter_id == "test_id"
        assert instance.mode == "test_mode"
        assert instance.adapter == mock_adapter
        assert instance.config_params == {"test": "value"}
        assert instance.loaded_at == now
        assert instance.is_running is False
        assert instance.services_registered == []
    
    def test_adapter_instance_post_init(self):
        """Test post-init initialization of services_registered."""
        instance = AdapterInstance(
            adapter_id="test",
            mode="test",
            adapter=MagicMock(),
            config_params={},
            loaded_at=datetime.now(timezone.utc),
            services_registered=None
        )
        
        assert instance.services_registered == []