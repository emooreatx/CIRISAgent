import pytest
from unittest.mock import MagicMock
from ciris_engine.action_handlers.speak_handler import SpeakHandler
from ciris_engine.schemas.action_params_v1 import SpeakParams
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies

@pytest.mark.asyncio
async def test_speak_handler_schema_driven(monkeypatch):
    # Dependency injection: mock dependencies
    deps = ActionHandlerDependencies(
        llm_service=MagicMock(),
        memory_service=MagicMock(),
        event_sink=MagicMock(),
        config=MagicMock(),
        logger=MagicMock(),
    )
    handler = SpeakHandler(deps)
    params = SpeakParams(content="Hello world!", channel_id="chan1")
    thought = Thought(
        thought_id="t1",
        source_task_id="s1",
        thought_type="speak",
        status="PENDING",
        created_at="2025-05-28T00:00:00Z",
        updated_at="2025-05-28T00:00:00Z",
        round_number=1,
        content="Say hi",
        context={},
        ponder_count=0,
        ponder_notes=None,
        parent_thought_id=None,
        final_action={}
    )
    # SUT: call handle
    result = await handler.handle(params, thought)
    # Assert schema-driven output (could be a dict or a model, depending on implementation)
    assert result is not None
    assert hasattr(result, "status") or isinstance(result, dict)
    assert params.content in str(result)
