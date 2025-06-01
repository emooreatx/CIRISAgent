import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.action_handlers.speak_handler import SpeakHandler
from ciris_engine.schemas.action_params_v1 import SpeakParams
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies
from ciris_engine.registries.base import ServiceRegistry, Priority

@pytest.mark.asyncio
async def test_speak_handler_schema_driven(monkeypatch):
    service_registry = ServiceRegistry()
    comm_service = AsyncMock()
    comm_service.send_message = AsyncMock(return_value=True)
    service_registry.register_global(
        service_type="communication",
        provider=comm_service,
        priority=Priority.HIGH,
        capabilities=["send_message"],
    )
    deps = ActionHandlerDependencies(service_registry=service_registry)
    handler = SpeakHandler(deps)

    action_result = ActionSelectionResult(
        selected_action=HandlerActionType.SPEAK,
        action_parameters=SpeakParams(content="Hello world!", channel_id="123"),
        rationale="r",
    )
    thought = Thought(
        thought_id="t1",
        source_task_id="s1",
        thought_type="speak",
        status=ThoughtStatus.PENDING,
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

    update_thought = MagicMock()
    add_thought = MagicMock()
    monkeypatch.setattr("ciris_engine.persistence.update_thought_status", update_thought)
    monkeypatch.setattr("ciris_engine.persistence.add_thought", add_thought)

    await handler.handle(action_result, thought, {"channel_id": "123"})

    comm_service.send_message.assert_awaited_with("123", "Hello world!")
    update_thought.assert_called_once()
    assert update_thought.call_args.kwargs["status"] == ThoughtStatus.COMPLETED
    add_thought.assert_called_once()


@pytest.mark.asyncio
async def test_speak_handler_missing_params(monkeypatch):
    service_registry = ServiceRegistry()
    comm_service = AsyncMock()
    comm_service.send_message = AsyncMock(return_value=True)
    service_registry.register_global(
        service_type="communication",
        provider=comm_service,
        priority=Priority.HIGH,
        capabilities=["send_message"],
    )
    deps = ActionHandlerDependencies(service_registry=service_registry)
    handler = SpeakHandler(deps)

    action_result = ActionSelectionResult(
        selected_action=HandlerActionType.SPEAK,
        action_parameters={},
        rationale="r",
    )
    thought = Thought(
        thought_id="t2",
        source_task_id="s2",
        thought_type="speak",
        status=ThoughtStatus.PENDING,
        created_at="2025-05-28T00:00:00Z",
        updated_at="2025-05-28T00:00:00Z",
        round_number=1,
        content="Say hi",
        context={},
        ponder_count=0,
        ponder_notes=None,
        parent_thought_id=None,
        final_action={},
    )

    update_thought = MagicMock()
    add_thought = MagicMock()
    monkeypatch.setattr("ciris_engine.persistence.update_thought_status", update_thought)
    monkeypatch.setattr("ciris_engine.persistence.add_thought", add_thought)

    await handler.handle(action_result, thought, {"channel_id": None})

    comm_service.send_message.assert_not_awaited()
    update_thought.assert_called_once()
    assert update_thought.call_args.kwargs["status"] == ThoughtStatus.FAILED
    add_thought.assert_called_once()
