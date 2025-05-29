import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.action_handlers.observe_handler import ObserveHandler
from ciris_engine.schemas.action_params_v1 import ObserveParams
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies


DEFAULT_THOUGHT_KWARGS = dict(
    thought_id="t1",
    source_task_id="task1",
    thought_type="test",
    status=ThoughtStatus.PENDING,
    created_at="now",
    updated_at="now",
    round_number=1,
    content="content",
    context={},
    ponder_count=0,
    ponder_notes=None,
    parent_thought_id=None,
    final_action={},
)


@pytest.mark.asyncio
async def test_observe_handler_active_injects_channel(monkeypatch):
    handle_event = AsyncMock()
    monkeypatch.setattr(
        "ciris_engine.action_handlers.observe_handler.handle_discord_observe_event",
        handle_event,
    )
    update_status = MagicMock()
    add_thought = MagicMock()
    monkeypatch.setattr("ciris_engine.persistence.update_thought_status", update_status)
    monkeypatch.setattr("ciris_engine.persistence.add_thought", add_thought)

    deps = ActionHandlerDependencies()
    handler = ObserveHandler(deps)

    params = ObserveParams(active=True, channel_id=None, context={})
    action_result = ActionSelectionResult.model_construct(
        selected_action=HandlerActionType.OBSERVE,
        action_parameters=params,
        rationale="r",
    )
    thought = Thought(**DEFAULT_THOUGHT_KWARGS)

    await handler.handle(action_result, thought, {"channel_id": "chanX"})

    handle_event.assert_awaited()
    payload = handle_event.call_args.kwargs["payload"]
    assert payload["channel_id"] == "chanX"
