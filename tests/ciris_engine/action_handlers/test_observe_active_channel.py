import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.action_handlers.observe_handler import ObserveHandler
from ciris_engine.schemas.action_params_v1 import ObserveParams
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus, ThoughtType
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope


DEFAULT_THOUGHT_KWARGS = dict(
    thought_id="t1",
    source_task_id="task1",
    thought_type=ThoughtType.STANDARD,
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
    update_status = MagicMock()
    add_thought = MagicMock()
    monkeypatch.setattr("ciris_engine.persistence.update_thought_status", update_status)
    monkeypatch.setattr("ciris_engine.persistence.add_thought", add_thought)

    mock_sink = AsyncMock()
    mock_sink.fetch_messages_sync = AsyncMock(return_value=[])
    deps = ActionHandlerDependencies()
    deps.get_multi_service_sink = lambda: mock_sink
    handler = ObserveHandler(deps)
    handler.get_multi_service_sink = lambda: mock_sink

    params = ObserveParams(active=True, channel_id=None, context={"source": "test"})
    action_result = ActionSelectionResult.model_construct(
        selected_action=HandlerActionType.OBSERVE,
        action_parameters=params,
        rationale="r",
    )
    thought = Thought(**DEFAULT_THOUGHT_KWARGS)

    await handler.handle(action_result, thought, {"channel_id": "chanX"})

    mock_sink.fetch_messages_sync.assert_awaited_with(
        handler_name="ObserveHandler",
        channel_id="chanX",
        limit=50,
        metadata={"active_observation": True},
    )
