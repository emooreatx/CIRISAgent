"""Tests for RuntimeAdapterManager"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from ciris_engine.runtime.adapter_manager import RuntimeAdapterManager, AdapterInstance


@pytest.fixture
def mock_runtime():
    """Mock runtime instance"""
    runtime = MagicMock()
    runtime.adapters = []
    runtime.service_registry = MagicMock()
    return runtime


@pytest.fixture
def mock_adapter():
    """Mock adapter instance"""
    from ciris_engine.protocols.adapter_interface import ServiceRegistration
    from ciris_engine.schemas.foundational_schemas_v1 import ServiceType
    from ciris_engine.registries.base import Priority
    
    adapter = AsyncMock()
    adapter.start = AsyncMock()
    adapter.stop = AsyncMock()
    
    # Create a real ServiceRegistration for testing
    mock_service = MagicMock()
    mock_service.__class__.__name__ = "MockCommunicationService"
    
    service_registration = ServiceRegistration(
        service_type=ServiceType.COMMUNICATION,
        provider=mock_service,
        priority=Priority.HIGH,
        handlers=["SpeakHandler", "ObserveHandler"],
        capabilities=["send_message", "receive_message"]
    )
    
    adapter.get_services_to_register = MagicMock(return_value=[service_registration])
    return adapter


@pytest.fixture 
def adapter_manager(mock_runtime):
    """RuntimeAdapterManager instance with mocked runtime"""
    return RuntimeAdapterManager(mock_runtime)


@pytest.mark.asyncio
async def test_adapter_manager_initialization(mock_runtime):
    """Test RuntimeAdapterManager initialization"""
    manager = RuntimeAdapterManager(mock_runtime)
    
    assert manager.runtime == mock_runtime
    assert manager.loaded_adapters == {}
    assert manager._adapter_counter == 0


@pytest.mark.asyncio
async def test_load_adapter_success(adapter_manager, mock_adapter):
    """Test successful adapter loading"""
    with patch('ciris_engine.runtime.adapter_manager.load_adapter') as mock_load_adapter:
        mock_load_adapter.return_value = lambda runtime, **kwargs: mock_adapter
        
        result = await adapter_manager.load_adapter("test_mode", "test_adapter", {"param": "value"})
        
        assert result["success"] is True
        assert result["adapter_id"] == "test_adapter"
        assert result["mode"] == "test_mode"
        assert "test_adapter" in adapter_manager.loaded_adapters
        
        # Check adapter was added to runtime
        assert mock_adapter in adapter_manager.runtime.adapters
        mock_adapter.start.assert_called_once()


@pytest.mark.asyncio
async def test_load_adapter_auto_id(adapter_manager, mock_adapter):
    """Test adapter loading with auto-generated ID"""
    with patch('ciris_engine.runtime.adapter_manager.load_adapter') as mock_load_adapter:
        mock_load_adapter.return_value = lambda runtime, **kwargs: mock_adapter
        
        result = await adapter_manager.load_adapter("test_mode")
        
        assert result["success"] is True
        assert result["adapter_id"] == "test_mode_1"
        assert "test_mode_1" in adapter_manager.loaded_adapters


@pytest.mark.asyncio
async def test_load_adapter_duplicate_id(adapter_manager, mock_adapter):
    """Test loading adapter with duplicate ID"""
    # First load
    with patch('ciris_engine.runtime.adapter_manager.load_adapter') as mock_load_adapter:
        mock_load_adapter.return_value = lambda runtime, **kwargs: mock_adapter
        await adapter_manager.load_adapter("test_mode", "duplicate_id")
        
        # Second load with same ID
        result = await adapter_manager.load_adapter("test_mode", "duplicate_id")
        
        assert result["success"] is False
        assert "already exists" in result["error"]


@pytest.mark.asyncio
async def test_load_adapter_error_handling(adapter_manager):
    """Test adapter loading error handling"""
    with patch('ciris_engine.runtime.adapter_manager.load_adapter') as mock_load_adapter:
        mock_load_adapter.side_effect = Exception("Test error")
        
        result = await adapter_manager.load_adapter("test_mode", "error_adapter")
        
        assert result["success"] is False
        assert "Test error" in result["error"]
        assert "error_adapter" not in adapter_manager.loaded_adapters


@pytest.mark.asyncio
async def test_unload_adapter_success(adapter_manager, mock_adapter):
    """Test successful adapter unloading"""
    # First load an adapter
    with patch('ciris_engine.runtime.adapter_manager.load_adapter') as mock_load_adapter:
        mock_load_adapter.return_value = lambda runtime, **kwargs: mock_adapter
        await adapter_manager.load_adapter("test_mode", "test_adapter")
        
        # Then unload it
        result = await adapter_manager.unload_adapter("test_adapter")
        
        assert result["success"] is True
        assert result["adapter_id"] == "test_adapter"
        assert "test_adapter" not in adapter_manager.loaded_adapters
        
        # Check adapter was removed from runtime
        assert mock_adapter not in adapter_manager.runtime.adapters
        mock_adapter.stop.assert_called_once()


@pytest.mark.asyncio
async def test_unload_adapter_not_found(adapter_manager):
    """Test unloading adapter that doesn't exist"""
    result = await adapter_manager.unload_adapter("nonexistent")
    
    assert result["success"] is False
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_unload_adapter_error_handling(adapter_manager, mock_adapter):
    """Test adapter unloading error handling"""
    # First load an adapter
    with patch('ciris_engine.runtime.adapter_manager.load_adapter') as mock_load_adapter:
        mock_load_adapter.return_value = lambda runtime, **kwargs: mock_adapter
        await adapter_manager.load_adapter("test_mode", "test_adapter")
        
        # Make stop() raise an exception
        mock_adapter.stop.side_effect = Exception("Stop error")
        
        result = await adapter_manager.unload_adapter("test_adapter")
        
        assert result["success"] is False
        assert "Stop error" in result["error"]


@pytest.mark.asyncio
async def test_list_adapters(adapter_manager, mock_adapter):
    """Test listing adapters"""
    # Load a couple of adapters
    with patch('ciris_engine.runtime.adapter_manager.load_adapter') as mock_load_adapter:
        mock_load_adapter.return_value = lambda runtime, **kwargs: mock_adapter
        await adapter_manager.load_adapter("test_mode", "adapter1")
        await adapter_manager.load_adapter("test_mode", "adapter2")
        
        result = await adapter_manager.list_adapters()
        
        assert len(result) == 2
        adapter_ids = [adapter["adapter_id"] for adapter in result]
        assert "adapter1" in adapter_ids
        assert "adapter2" in adapter_ids


@pytest.mark.asyncio
async def test_list_adapters_empty(adapter_manager):
    """Test listing adapters when none are loaded"""
    result = await adapter_manager.list_adapters()
    
    assert result == []


@pytest.mark.asyncio
async def test_get_adapter_status_success(adapter_manager, mock_adapter):
    """Test getting adapter status"""
    # Load an adapter first
    with patch('ciris_engine.runtime.adapter_manager.load_adapter') as mock_load_adapter:
        mock_load_adapter.return_value = lambda runtime, **kwargs: mock_adapter
        await adapter_manager.load_adapter("test_mode", "test_adapter")
        
        result = await adapter_manager.get_adapter_status("test_adapter")
        
        assert result["success"] is True
        assert result["adapter_id"] == "test_adapter"
        assert result["mode"] == "test_mode"
        assert result["is_running"] is True


@pytest.mark.asyncio
async def test_get_adapter_status_not_found(adapter_manager):
    """Test getting status of adapter that doesn't exist"""
    result = await adapter_manager.get_adapter_status("nonexistent")
    
    assert result["success"] is False
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_get_adapter_info_success(adapter_manager, mock_adapter):
    """Test getting detailed adapter info"""
    # Load an adapter first
    with patch('ciris_engine.runtime.adapter_manager.load_adapter') as mock_load_adapter:
        mock_load_adapter.return_value = lambda runtime, **kwargs: mock_adapter
        await adapter_manager.load_adapter("test_mode", "test_adapter", {"config_key": "config_value"})
        
        result = await adapter_manager.get_adapter_info("test_adapter")
        
        assert result["adapter_id"] == "test_adapter"
        assert result["mode"] == "test_mode"
        assert result["config"]["config_key"] == "config_value"
        assert "load_time" in result
        assert result["is_running"] is True


@pytest.mark.asyncio
async def test_get_adapter_info_not_found(adapter_manager):
    """Test getting info of adapter that doesn't exist"""
    result = await adapter_manager.get_adapter_info("nonexistent")
    
    assert result == {}


@pytest.mark.asyncio
async def test_reload_adapter_success(adapter_manager, mock_adapter):
    """Test reloading adapter with new config"""
    # Load an adapter first
    with patch('ciris_engine.runtime.adapter_manager.load_adapter') as mock_load_adapter:
        mock_load_adapter.return_value = lambda runtime, **kwargs: mock_adapter
        await adapter_manager.load_adapter("test_mode", "test_adapter", {"old_config": "old_value"})
        
        # Reload with new config
        result = await adapter_manager.reload_adapter("test_adapter", {"new_config": "new_value"})
        
        assert result["success"] is True
        assert result["adapter_id"] == "test_adapter"
        
        # Check that the adapter was reloaded
        instance = adapter_manager.loaded_adapters["test_adapter"]
        assert instance.config_params["new_config"] == "new_value"
        assert "old_config" not in instance.config_params


@pytest.mark.asyncio
async def test_reload_adapter_not_found(adapter_manager):
    """Test reloading adapter that doesn't exist"""
    result = await adapter_manager.reload_adapter("nonexistent", {})
    
    assert result["success"] is False
    assert "not found" in result["error"]


def test_adapter_instance_creation():
    """Test AdapterInstance dataclass"""
    mock_adapter = MagicMock()
    now = datetime.now(timezone.utc)
    
    instance = AdapterInstance(
        adapter_id="test_id",
        mode="test_mode", 
        adapter=mock_adapter,
        config_params={"key": "value"},
        loaded_at=now,
        is_running=True
    )
    
    assert instance.adapter_id == "test_id"
    assert instance.mode == "test_mode"
    assert instance.adapter == mock_adapter
    assert instance.config_params == {"key": "value"}
    assert instance.loaded_at == now
    assert instance.is_running is True
    assert instance.services_registered == []  # Default from __post_init__


@pytest.mark.asyncio
async def test_register_adapter_services(adapter_manager, mock_adapter):
    """Test service registration during adapter loading"""
    # Mock adapter fixture already has proper ServiceRegistration
    
    with patch('ciris_engine.runtime.adapter_manager.load_adapter') as mock_load_adapter:
        mock_load_adapter.return_value = lambda runtime, **kwargs: mock_adapter
        
        result = await adapter_manager.load_adapter("test_mode", "test_adapter")
        
        assert result["success"] is True
        # Check that services were registered
        instance = adapter_manager.loaded_adapters["test_adapter"]
        assert len(instance.services_registered) > 0
        # Should have 2 registrations (SpeakHandler and ObserveHandler)
        assert len(instance.services_registered) == 2