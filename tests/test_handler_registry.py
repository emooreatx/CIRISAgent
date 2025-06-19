def test_memory_handlers_registered():
    from ciris_engine.action_handlers.handler_registry import build_action_dispatcher
    from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
    from unittest.mock import AsyncMock
    from ciris_engine.message_buses import BusManager
    
    # Create a mock bus manager
    mock_service_registry = AsyncMock()
    bus_manager = BusManager(mock_service_registry)
    
    dispatcher = build_action_dispatcher(bus_manager)
    # Verify all memory handlers are registered
    assert HandlerActionType.MEMORIZE in dispatcher.handlers
    assert HandlerActionType.RECALL in dispatcher.handlers
    assert HandlerActionType.FORGET in dispatcher.handlers
