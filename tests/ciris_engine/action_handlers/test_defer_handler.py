import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from ciris_engine.action_handlers.defer_handler import DeferHandler
from ciris_engine.schemas.action_params_v1 import DeferParams, MemorizeParams
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus, ThoughtType
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope

now = datetime.utcnow()

@pytest.mark.asyncio
async def test_defer_handler_schema_driven(monkeypatch):
    wa_service = AsyncMock()
    service_registry = AsyncMock()
    
    async def get_service(handler, service_type, **kwargs):
        if service_type == "wise_authority":
            return wa_service
        return None
    
    service_registry.get_service = AsyncMock(side_effect=get_service)
    deps = ActionHandlerDependencies(
        service_registry=service_registry
    )
    handler = DeferHandler(deps)

    action_result = ActionSelectionResult(
        selected_action=HandlerActionType.DEFER,
        action_parameters=DeferParams(reason=GraphNode(id=NodeType.USER, type=NodeType.USER, scope=GraphScope.IDENTITY), context={"foo": "bar"}),
        rationale="r",
    )
    thought = Thought(
        thought_id="t1",
        source_task_id="task1",
        thought_type=ThoughtType.FOLLOW_UP,
        status=ThoughtStatus.PENDING,
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
        round_number=0,
        content="test content",
        context={},
        ponder_count=0,
        parent_thought_id=None,
        final_action={}
    )

    update_thought = MagicMock()
    update_task = MagicMock()
    monkeypatch.setattr("ciris_engine.persistence.update_thought_status", update_thought)
    monkeypatch.setattr("ciris_engine.persistence.update_task_status", update_task)

    await handler.handle(action_result, thought, {"channel_id": "chan1", "source_task_id": "s1"})

    wa_service.send_deferral.assert_awaited()
    update_thought.assert_called_once()
    assert update_thought.call_args.kwargs["status"] == ThoughtStatus.DEFERRED
    update_task.assert_called_once()
