import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.message_buses import BusManager
from ciris_engine.registries.base import ServiceRegistry, Priority


@pytest.mark.asyncio
async def test_bus_manager_creation():
    """Test that BusManager can be created and started."""
    registry = ServiceRegistry()
    bus_manager = BusManager(registry)
    
    # Test that all buses are created
    assert hasattr(bus_manager, 'communication')
    assert hasattr(bus_manager, 'memory')
    assert hasattr(bus_manager, 'tool')
    assert hasattr(bus_manager, 'audit')
    assert hasattr(bus_manager, 'telemetry')
    assert hasattr(bus_manager, 'wise')
    assert hasattr(bus_manager, 'llm')
    
    # Test lifecycle methods
    await bus_manager.start()
    await bus_manager.stop()


@pytest.mark.asyncio
async def test_bus_manager_communication():
    """Test communication through bus manager."""
    registry = ServiceRegistry()
    
    # Register a mock communication service
    mock_comm_service = AsyncMock()
    mock_comm_service.send_message = AsyncMock(return_value=True)
    registry.register_global(
        service_type="communication",
        provider=mock_comm_service,
        priority=Priority.HIGH,
        capabilities=["send_message"]
    )
    
    bus_manager = BusManager(registry)
    # Don't start the bus manager to avoid the async processing loop
    
    # Test sending a message synchronously
    result = await bus_manager.communication.send_message_sync(
        channel_id="test_channel",
        content="Hello world",
        handler_name="TestHandler"
    )
    
    assert result is True
    # The bus calls the service with just channel_id and content
    mock_comm_service.send_message.assert_called_once_with("test_channel", "Hello world")


@pytest.mark.asyncio
async def test_bus_manager_audit():
    """Test audit logging through bus manager."""
    registry = ServiceRegistry()
    
    # Register a mock audit service
    mock_audit_service = AsyncMock()
    mock_audit_service.log_event = AsyncMock(return_value="tx123")
    registry.register_global(
        service_type="audit",
        provider=mock_audit_service,
        priority=Priority.HIGH,
        capabilities=["log_event"]
    )
    
    bus_manager = BusManager(registry)
    # Don't start the bus manager to avoid the async processing loop
    
    # Test logging an audit event
    await bus_manager.audit.log_event(
        event_type="test_event",
        event_data={"test": "data"},
        handler_name="TestHandler"
    )
    
    # Verify the service was called
    mock_audit_service.log_event.assert_called_once_with(
        event_type="test_event",
        event_data={"test": "data"}
    )


@pytest.mark.asyncio
async def test_bus_manager_health_check():
    """Test health check functionality."""
    registry = ServiceRegistry()
    bus_manager = BusManager(registry)
    
    await bus_manager.start()
    
    # Test health check
    health = await bus_manager.health_check()
    
    # All buses should be reported
    assert "communication" in health
    assert "memory" in health
    assert "tool" in health
    assert "audit" in health
    assert "telemetry" in health
    assert "wise" in health
    assert "llm" in health
    
    await bus_manager.stop()


@pytest.mark.asyncio
async def test_bus_manager_stats():
    """Test statistics gathering."""
    registry = ServiceRegistry()
    bus_manager = BusManager(registry)
    
    await bus_manager.start()
    
    # Test getting stats
    stats = bus_manager.get_stats()
    
    # All buses should have stats
    assert "communication" in stats
    assert "memory" in stats
    assert "tool" in stats
    assert "audit" in stats
    assert "telemetry" in stats
    assert "wise" in stats
    assert "llm" in stats
    
    # Test total queue size
    total_size = bus_manager.get_total_queue_size()
    assert isinstance(total_size, int)
    assert total_size >= 0
    
    await bus_manager.stop()


# Note: The original MultiServiceTransactionOrchestrator has been replaced
# with BusManager which provides better separation of concerns and typed
# interfaces for each service type.