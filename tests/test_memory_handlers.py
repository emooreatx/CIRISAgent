from unittest.mock import Mock, AsyncMock
from ciris_engine.action_handlers.memorize_handler import MemorizeHandler
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies
from ciris_engine.schemas.context_schemas_v1 import ThoughtContext, SystemSnapshot

def test_memorize_handler_with_new_schema(monkeypatch):
    # Setup
    memory_service = Mock()
    memory_service.memorize = AsyncMock(return_value=Mock(status=Mock(value="ok")))
    deps = ActionHandlerDependencies()
    async def get_service(handler, service_type, **kwargs):
        if service_type == "memory":
            return memory_service
        return None
    deps.get_service = AsyncMock(side_effect=get_service)
    # Patch persistence functions and helper
    monkeypatch.setattr("ciris_engine.persistence.update_thought_status", Mock())
    monkeypatch.setattr("ciris_engine.persistence.add_thought", Mock())
    def mock_create_follow_up_thought(parent, content):
        mock_thought = Mock()
        mock_thought.thought_id = "follow_up_test"
        # Create a real ThoughtContext object that can be dumped and validated
        mock_thought.context = ThoughtContext(system_snapshot=SystemSnapshot())
        return mock_thought
    
    monkeypatch.setattr(
        "ciris_engine.action_handlers.memorize_handler.create_follow_up_thought",
        mock_create_follow_up_thought
    )
    
    handler = MemorizeHandler(deps)
    
    # Test new schema
    node = {"id": "test", "type": "user", "scope": "local", "attributes": {"value": "data"}}
    result = ActionSelectionResult(
        selected_action=HandlerActionType.MEMORIZE,
        action_parameters={"node": node},
        rationale="test"
    )
    
    thought = Mock(thought_id="test_thought", source_task_id="test_task")
    
    import asyncio
    asyncio.run(handler.handle(result, thought, {"channel_id": "test"}))
    
    # Verify memory service was called correctly
    assert memory_service.memorize.called

def test_memorize_handler_with_old_schema(monkeypatch):
    # Test backward compatibility
    memory_service = Mock()
    memory_service.memorize = AsyncMock(return_value=Mock(status=Mock(value="ok")))
    deps = ActionHandlerDependencies()
    async def get_service(handler, service_type, **kwargs):
        if service_type == "memory":
            return memory_service
        return None
    deps.get_service = AsyncMock(side_effect=get_service)
    monkeypatch.setattr("ciris_engine.persistence.update_thought_status", Mock())
    monkeypatch.setattr("ciris_engine.persistence.add_thought", Mock())
    def mock_create_follow_up_thought(parent, content):
        mock_thought = Mock()
        mock_thought.thought_id = "follow_up_test"
        # Create a real ThoughtContext object that can be dumped and validated
        mock_thought.context = ThoughtContext(system_snapshot=SystemSnapshot())
        return mock_thought
    
    monkeypatch.setattr(
        "ciris_engine.action_handlers.memorize_handler.create_follow_up_thought",
        mock_create_follow_up_thought
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
    assert memory_service.memorize.called
