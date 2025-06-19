import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.action_handlers.observe_handler import ObserveHandler
from ciris_engine.schemas.action_params_v1 import ObserveParams
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus, ThoughtType
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies
from ciris_engine.message_buses.bus_manager import BusManager
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope
from tests.helpers import create_test_dispatch_context
from ciris_engine.utils.channel_utils import create_channel_context


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
    thought_depth=0,
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

    mock_service_registry = AsyncMock()
    bus_manager = BusManager(mock_service_registry)
    
    # Mock the communication bus to have fetch_messages method
    mock_communication_bus = AsyncMock()
    mock_communication_bus.fetch_messages = AsyncMock(return_value=[])
    bus_manager.communication = mock_communication_bus
    
    # Mock the memory bus for recall operations
    mock_memory_bus = AsyncMock()
    mock_memory_bus.recall = AsyncMock()
    bus_manager.memory = mock_memory_bus
    
    deps = ActionHandlerDependencies(bus_manager=bus_manager)
    handler = ObserveHandler(deps)

    params = ObserveParams(active=True, channel_context=create_channel_context(None), context={"source": "test"})
    action_result = ActionSelectionResult.model_construct(
        selected_action=HandlerActionType.OBSERVE,
        action_parameters=params,
        rationale="r",
    )
    thought = Thought(**DEFAULT_THOUGHT_KWARGS)

    context = create_test_dispatch_context(channel_id="chanX", action_type=HandlerActionType.OBSERVE)
    await handler.handle(action_result, thought, context)

    mock_communication_bus.fetch_messages.assert_awaited_with(
        handler_name="ObserveHandler",
        channel_id="chanX",
        limit=50
    )
