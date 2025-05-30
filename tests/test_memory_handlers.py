from unittest.mock import Mock, AsyncMock
from ciris_engine.action_handlers.memorize_handler import MemorizeHandler
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies

def test_memorize_handler_with_new_schema(monkeypatch):
    # Setup
    memory_service = Mock()
    memory_service.memorize = AsyncMock(return_value=Mock(status=Mock(value="ok")))
    deps = ActionHandlerDependencies()
    deps.get_service = AsyncMock(return_value=memory_service)
    deps.memory_service = memory_service
    deps.audit_service = None
    # Patch persistence functions and helper
    monkeypatch.setattr("ciris_engine.persistence.update_thought_status", Mock())
    monkeypatch.setattr("ciris_engine.persistence.add_thought", Mock())
    monkeypatch.setattr(
        "ciris_engine.action_handlers.memorize_handler.create_follow_up_thought",
        lambda parent, content: Mock()
    )
    
    handler = MemorizeHandler(deps)
    
    # Test new schema
    result = ActionSelectionResult(
        selected_action=HandlerActionType.MEMORIZE,
        action_parameters={"key": "test", "value": "data", "scope": "local"},
        rationale="test"
    )
    
    thought = Mock(thought_id="test_thought", source_task_id="test_task")
    
    import asyncio
    asyncio.run(handler.handle(result, thought, {"channel_id": "test"}))
    
    # Verify memory service was called correctly
    assert deps.memory_service.memorize.called

def test_memorize_handler_with_old_schema(monkeypatch):
    # Test backward compatibility
    memory_service = Mock()
    memory_service.memorize = AsyncMock(return_value=Mock(status=Mock(value="ok")))
    deps = ActionHandlerDependencies()
    deps.get_service = AsyncMock(return_value=memory_service)
    deps.memory_service = memory_service
    deps.audit_service = None
    monkeypatch.setattr("ciris_engine.persistence.update_thought_status", Mock())
    monkeypatch.setattr("ciris_engine.persistence.add_thought", Mock())
    monkeypatch.setattr(
        "ciris_engine.action_handlers.memorize_handler.create_follow_up_thought",
        lambda parent, content: Mock()
    )
    handler = MemorizeHandler(deps)
    result = ActionSelectionResult(
        selected_action=HandlerActionType.MEMORIZE,
        action_parameters={
            "knowledge_unit_description": "test",
            "knowledge_data": {"value": "data"},
            "knowledge_type": "test_type"
        },
        rationale="test"
    )
    thought = Mock(thought_id="test_thought", source_task_id="test_task")
    import asyncio
    asyncio.run(handler.handle(result, thought, {"channel_id": "test"}))
    assert deps.memory_service.memorize.called
