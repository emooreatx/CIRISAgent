import pytest
from unittest.mock import MagicMock
from ciris_engine.action_handlers.defer_handler import DeferHandler
from ciris_engine.schemas.action_params_v1 import DeferParams
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies

@pytest.mark.asyncio
async def test_defer_handler_schema_driven(monkeypatch):
    deps = ActionHandlerDependencies(
        llm_service=MagicMock(),
        memory_service=MagicMock(),
        event_sink=MagicMock(),
        config=MagicMock(),
        logger=MagicMock(),
    )
    handler = DeferHandler(deps)
    params = DeferParams(reason="Need WA", context={"foo": "bar"})
    thought = Thought(
        thought_id="t1",
        source_task_id="s1",
        thought_type="defer",
        status="PENDING",
        created_at="2025-05-28T00:00:00Z",
        updated_at="2025-05-28T00:00:00Z",
        round_number=1,
        content="Defer this",
        context={},
        ponder_count=0,
        ponder_notes=None,
        parent_thought_id=None,
        final_action={}
    )
    result = await handler.handle(params, thought)
    assert result is not None
    assert hasattr(result, "status") or isinstance(result, dict)
    assert params.reason in str(result)
