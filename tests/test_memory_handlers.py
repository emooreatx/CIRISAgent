import pytest
from unittest.mock import Mock, AsyncMock
from ciris_engine.action_handlers.memorize_handler import MemorizeHandler
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType

@pytest.mark.asyncio
async def test_memorize_handler_with_new_schema():
    # Setup
    deps = Mock()
    deps.memory_service = AsyncMock()
    deps.memory_service.memorize.return_value = Mock(status=Mock(value="ok"))
    
    handler = MemorizeHandler(deps)
    
    # Test new schema
    result = ActionSelectionResult(
        selected_action=HandlerActionType.MEMORIZE,
        action_parameters={"key": "test", "value": "data", "scope": "local"},
        rationale="test"
    )
    
    thought = Mock(thought_id="test_thought", source_task_id="test_task")
    
    await handler.handle(result, thought, {"channel_id": "test"})
    
    # Verify memory service was called correctly
    assert deps.memory_service.memorize.called

@pytest.mark.asyncio
async def test_memorize_handler_with_old_schema():
    # Test backward compatibility
    deps = Mock()
    deps.memory_service = AsyncMock()
    deps.memory_service.memorize.return_value = Mock(status=Mock(value="ok"))
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
    await handler.handle(result, thought, {"channel_id": "test"})
    assert deps.memory_service.memorize.called
