import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.action_handlers.defer_handler import DeferHandler
from ciris_engine.schemas.action_params_v1 import DeferParams
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies

@pytest.mark.asyncio
async def test_defer_handler_schema_driven(monkeypatch):
    action_sink = AsyncMock()
    deps = ActionHandlerDependencies(
        action_sink=action_sink,
        memory_service=MagicMock(),
    )
    handler = DeferHandler(deps)

    action_result = ActionSelectionResult(
        selected_action=HandlerActionType.DEFER,
        action_parameters=DeferParams(reason="Need WA", context={"foo": "bar"}).model_dump(),
        rationale="r",
    )
    thought = Thought(
        thought_id="t1",
        source_task_id="s1",
        thought_type="defer",
        status=ThoughtStatus.PENDING,
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

    update_thought = MagicMock()
    update_task = MagicMock()
    monkeypatch.setattr("ciris_engine.persistence.update_thought_status", update_thought)
    monkeypatch.setattr("ciris_engine.persistence.update_task_status", update_task)

    await handler.handle(action_result, thought, {"channel_id": "chan1", "source_task_id": "s1"})

    action_sink.submit_deferral.assert_awaited()
    assert "deferral_package" in action_sink.submit_deferral.call_args.args[3]
    update_thought.assert_called_once()
    assert update_thought.call_args.kwargs["status"] == ThoughtStatus.DEFERRED
    update_task.assert_called_once()
