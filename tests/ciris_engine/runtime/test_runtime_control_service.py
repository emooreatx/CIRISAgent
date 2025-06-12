"""Tests for RuntimeControlService"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from ciris_engine.runtime.runtime_control import RuntimeControlService
from ciris_engine.schemas.runtime_control_schemas import ProcessorStatus


@pytest.fixture
def mock_runtime():
    """Mock runtime instance"""
    runtime = MagicMock()
    runtime.adapters = []
    return runtime


@pytest.fixture
def mock_telemetry_collector():
    """Mock telemetry collector"""
    collector = AsyncMock()
    collector.single_step = AsyncMock(return_value={"thoughts_processed": 1})
    collector.pause_processing = AsyncMock()
    collector.resume_processing = AsyncMock()
    collector.get_processing_queue_status = AsyncMock(return_value={"queue_size": 0})
    return collector


@pytest.fixture
def mock_adapter_manager():
    """Mock adapter manager"""
    manager = AsyncMock()
    manager.load_adapter = AsyncMock(return_value={"success": True, "adapter_id": "test_adapter"})
    manager.unload_adapter = AsyncMock(return_value={"success": True, "mode": "test"})
    manager.list_adapters = AsyncMock(return_value=[])
    manager.get_adapter_info = AsyncMock(return_value={"status": "active"})
    return manager


@pytest.fixture
def mock_config_manager():
    """Mock config manager"""
    manager = AsyncMock()
    manager.get_config_value = AsyncMock(return_value={"key": "value"})
    manager.update_config_value = AsyncMock()
    manager.validate_config = AsyncMock()
    manager.reload_profile = AsyncMock()
    manager.list_profiles = AsyncMock(return_value=[])
    return manager


@pytest.fixture
def runtime_control_service(mock_runtime, mock_telemetry_collector, mock_adapter_manager, mock_config_manager):
    """RuntimeControlService instance with mocked dependencies"""
    return RuntimeControlService(
        telemetry_collector=mock_telemetry_collector,
        adapter_manager=mock_adapter_manager,
        config_manager=mock_config_manager,
        runtime=mock_runtime
    )


@pytest.mark.asyncio
async def test_runtime_control_service_initialization(mock_runtime):
    """Test RuntimeControlService initialization"""
    service = RuntimeControlService(runtime=mock_runtime)
    
    assert service.runtime == mock_runtime
    assert service._processor_status == ProcessorStatus.RUNNING
    assert isinstance(service._start_time, datetime)
    assert service._last_config_change is None
    assert service._events_history == []


@pytest.mark.asyncio
async def test_single_step_success(runtime_control_service, mock_telemetry_collector):
    """Test successful single step execution"""
    result = await runtime_control_service.single_step()
    
    assert result.success is True
    assert result.action == "single_step"
    assert result.result == {"thoughts_processed": 1}
    mock_telemetry_collector.single_step.assert_called_once()


@pytest.mark.asyncio
async def test_single_step_no_telemetry_collector():
    """Test single step when telemetry collector is not available"""
    service = RuntimeControlService()
    result = await service.single_step()
    
    assert result.success is False
    assert result.error == "Telemetry collector not available"


@pytest.mark.asyncio
async def test_pause_processing(runtime_control_service, mock_telemetry_collector):
    """Test pause processing"""
    result = await runtime_control_service.pause_processing()
    
    assert result.success is True
    assert result.action == "pause"
    assert result.result == {"status": "paused"}
    assert runtime_control_service._processor_status == ProcessorStatus.PAUSED
    mock_telemetry_collector.pause_processing.assert_called_once()


@pytest.mark.asyncio
async def test_resume_processing(runtime_control_service, mock_telemetry_collector):
    """Test resume processing"""
    result = await runtime_control_service.resume_processing()
    
    assert result.success is True
    assert result.action == "resume"
    assert result.result == {"status": "running"}
    assert runtime_control_service._processor_status == ProcessorStatus.RUNNING
    mock_telemetry_collector.resume_processing.assert_called_once()


@pytest.mark.asyncio
async def test_get_processor_queue_status(runtime_control_service, mock_telemetry_collector):
    """Test get processor queue status"""
    result = await runtime_control_service.get_processor_queue_status()
    
    assert result == {"queue_size": 0}
    mock_telemetry_collector.get_processing_queue_status.assert_called_once()


@pytest.mark.asyncio
async def test_load_adapter_success(runtime_control_service, mock_adapter_manager):
    """Test successful adapter loading"""
    result = await runtime_control_service.load_adapter(
        "discord", "test_adapter", {"token": "test_token"}, True
    )
    
    assert result.success is True
    assert result.adapter_id == "test_adapter"
    assert result.adapter_type == "discord"
    mock_adapter_manager.load_adapter.assert_called_once_with(
        "discord", "test_adapter", {"token": "test_token"}
    )


@pytest.mark.asyncio
async def test_load_adapter_no_manager():
    """Test adapter loading when adapter manager is not available"""
    service = RuntimeControlService()
    result = await service.load_adapter("discord", "test_adapter", {}, True)
    
    assert result.success is False
    assert result.error == "Adapter manager not available"


@pytest.mark.asyncio
async def test_unload_adapter_success(runtime_control_service, mock_adapter_manager):
    """Test successful adapter unloading"""
    result = await runtime_control_service.unload_adapter("test_adapter", False)
    
    assert result.success is True
    assert result.adapter_id == "test_adapter"
    mock_adapter_manager.unload_adapter.assert_called_once_with("test_adapter")


@pytest.mark.asyncio
async def test_list_adapters(runtime_control_service, mock_adapter_manager):
    """Test list adapters"""
    mock_adapter_manager.list_adapters.return_value = [{"id": "adapter1"}, {"id": "adapter2"}]
    
    result = await runtime_control_service.list_adapters()
    
    assert len(result) == 2
    assert result[0]["id"] == "adapter1"
    mock_adapter_manager.list_adapters.assert_called_once()


@pytest.mark.asyncio
async def test_list_adapters_no_manager():
    """Test list adapters when adapter manager is not available"""
    service = RuntimeControlService()
    result = await service.list_adapters()
    
    assert result == []


@pytest.mark.asyncio
async def test_get_adapter_info(runtime_control_service, mock_adapter_manager):
    """Test get adapter info"""
    mock_adapter_manager.get_adapter_info.return_value = {"status": "active", "id": "test_adapter"}
    
    result = await runtime_control_service.get_adapter_info("test_adapter")
    
    assert result["status"] == "active"
    assert result["id"] == "test_adapter"
    mock_adapter_manager.get_adapter_info.assert_called_once_with("test_adapter")


@pytest.mark.asyncio
async def test_get_adapter_info_no_manager():
    """Test get adapter info when adapter manager is not available"""
    service = RuntimeControlService()
    result = await service.get_adapter_info("test_adapter")
    
    assert result == {"error": "Adapter manager not available"}


@pytest.mark.asyncio
async def test_get_config(runtime_control_service, mock_config_manager):
    """Test get configuration"""
    mock_config_manager.get_config_value.return_value = {"llm": {"model": "gpt-4"}}
    
    result = await runtime_control_service.get_config("llm.model", False)
    
    assert result == {"llm": {"model": "gpt-4"}}
    mock_config_manager.get_config_value.assert_called_once_with("llm.model", False)


@pytest.mark.asyncio
async def test_get_runtime_status(runtime_control_service):
    """Test get runtime status"""
    runtime_control_service._processor_status = ProcessorStatus.RUNNING
    
    result = await runtime_control_service.get_runtime_status()
    
    assert result.processor_status == ProcessorStatus.RUNNING
    assert result.active_adapters == []
    assert result.loaded_adapters == []
    assert result.current_profile == "default"
    assert result.uptime_seconds > 0


@pytest.mark.asyncio 
async def test_event_recording(runtime_control_service):
    """Test event recording functionality"""
    await runtime_control_service._record_event(
        "test_category", 
        "test_action", 
        True, 
        {"key": "value"}, 
        None
    )
    
    assert len(runtime_control_service._events_history) == 1
    event = runtime_control_service._events_history[0]
    assert event["category"] == "test_category"
    assert event["action"] == "test_action"
    assert event["success"] is True
    assert event["result"] == {"key": "value"}


@pytest.mark.asyncio
async def test_get_events_history(runtime_control_service):
    """Test get events history"""
    # Add some test events
    await runtime_control_service._record_event("cat1", "action1", True)
    await runtime_control_service._record_event("cat2", "action2", False, error="test error")
    
    history = runtime_control_service.get_events_history(limit=5)
    
    assert len(history) == 2
    assert history[0]["category"] == "cat1"
    assert history[1]["category"] == "cat2"
    assert history[1]["error"] == "test error"


@pytest.mark.asyncio
async def test_shutdown_runtime(runtime_control_service):
    """Test runtime shutdown"""
    with patch('ciris_engine.utils.shutdown_manager.request_global_shutdown') as mock_shutdown:
        result = await runtime_control_service.shutdown_runtime("Test shutdown")
        
        assert result.success is True
        assert result.action == "shutdown"
        assert result.result["reason"] == "Test shutdown"
        assert runtime_control_service._processor_status == ProcessorStatus.STOPPED
        mock_shutdown.assert_called_once_with("Runtime control: Test shutdown")


@pytest.mark.asyncio
async def test_error_handling_in_single_step(runtime_control_service, mock_telemetry_collector):
    """Test error handling in single step"""
    mock_telemetry_collector.single_step.side_effect = Exception("Test error")
    
    result = await runtime_control_service.single_step()
    
    assert result.success is False
    assert "Test error" in result.error
    
    # Check that error was recorded in history
    assert len(runtime_control_service._events_history) == 1
    event = runtime_control_service._events_history[0]
    assert event["success"] is False
    assert "Test error" in event["error"]