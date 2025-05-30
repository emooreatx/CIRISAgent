import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.action_handlers.forget_handler import ForgetHandler
from ciris_engine.action_handlers.recall_handler import RecallHandler
from ciris_engine.action_handlers.observe_handler import ObserveHandler
from ciris_engine.action_handlers.reject_handler import RejectHandler
from ciris_engine.action_handlers.task_complete_handler import TaskCompleteHandler
from ciris_engine.action_handlers.tool_handler import ToolHandler, ToolResult, ToolExecutionStatus, ToolRegistry
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies
from ciris_engine.schemas.action_params_v1 import (
    ForgetParams,
    RecallParams,
    ObserveParams,
    RejectParams,
    ToolParams,
)
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, Task
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.graph_schemas_v1 import GraphScope, GraphNode, NodeType
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus, TaskStatus
from ciris_engine.adapters.local_graph_memory import MemoryOpResult, MemoryOpStatus


DEFAULT_THOUGHT_KWARGS = dict(
    thought_id="t1",
    source_task_id="task1",
    thought_type="test",
    status=ThoughtStatus.PENDING,
    created_at="2025-05-28T00:00:00Z",
    updated_at="2025-05-28T00:00:00Z",
    round_number=1,
    content="content",
    context={},
    ponder_count=0,
    ponder_notes=None,
    parent_thought_id=None,
    final_action={},
)


@pytest.mark.asyncio
async def test_forget_handler_schema_driven(monkeypatch):
    memory_service = AsyncMock()
    memory_service.forget.return_value = MemoryOpResult(status=MemoryOpStatus.OK)
    deps = ActionHandlerDependencies(memory_service=memory_service)
    deps.persistence = MagicMock()
    handler = ForgetHandler(deps)

    action_result = ActionSelectionResult.model_construct(
        selected_action=HandlerActionType.FORGET,
        action_parameters=ForgetParams(key="user1", scope="local", reason="r"),
        rationale="r",
    )
    thought = Thought(**DEFAULT_THOUGHT_KWARGS)

    await handler.handle(action_result, thought, {})

    expected_node = GraphNode(
        id="user1",
        type=NodeType.USER,
        scope=GraphScope.LOCAL,
        attributes={},
    )
    memory_service.forget.assert_awaited_with(expected_node)
    deps.persistence.add_thought.assert_called_once()


@pytest.mark.asyncio
async def test_recall_handler_schema_driven(monkeypatch):
    memory_service = AsyncMock()
    memory_service.recall.return_value = MemoryOpResult(
        status=MemoryOpStatus.OK, data={"foo": "bar"}
    )
    deps = ActionHandlerDependencies(memory_service=memory_service)
    deps.persistence = MagicMock()
    handler = RecallHandler(deps)

    action_result = ActionSelectionResult.model_construct(
        selected_action=HandlerActionType.RECALL,
        action_parameters=RecallParams(query="user1", scope="local"),
        rationale="r",
    )
    thought = Thought(**DEFAULT_THOUGHT_KWARGS)

    await handler.handle(action_result, thought, {})

    expected_node = GraphNode(
        id="user1",
        type=NodeType.USER,
        scope=GraphScope.LOCAL,
        attributes={},
    )
    memory_service.recall.assert_awaited_with(expected_node)
    deps.persistence.add_thought.assert_called_once()


@pytest.mark.asyncio
async def test_observe_handler_passive(monkeypatch):
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

    params = ObserveParams(active=False, context={})
    action_result = ActionSelectionResult.model_construct(
        selected_action=HandlerActionType.OBSERVE,
        action_parameters=params,
        rationale="r",
    )
    thought = Thought(**DEFAULT_THOUGHT_KWARGS)

    await handler.handle(action_result, thought, {})

    handle_event.assert_awaited()
    update_status.assert_called_once()
    add_thought.assert_called_once()


@pytest.mark.asyncio
async def test_reject_handler_schema_driven(monkeypatch):
    action_sink = AsyncMock()
    update_status = MagicMock()
    add_thought = MagicMock()
    monkeypatch.setattr("ciris_engine.persistence.update_thought_status", update_status)
    monkeypatch.setattr("ciris_engine.persistence.add_thought", add_thought)

    deps = ActionHandlerDependencies(action_sink=action_sink)
    handler = RejectHandler(deps)

    action_result = ActionSelectionResult.model_construct(
        selected_action=HandlerActionType.REJECT,
        action_parameters=RejectParams(reason="bad"),
        rationale="r",
    )
    thought = Thought(**DEFAULT_THOUGHT_KWARGS)

    await handler.handle(action_result, thought, {"channel_id": "chan"})

    action_sink.send_message.assert_awaited_with("chan", "Unable to proceed: bad")
    update_status.assert_called_once()
    add_thought.assert_called_once()
    assert update_status.call_args.kwargs["status"] == ThoughtStatus.FAILED


@pytest.mark.asyncio
async def test_task_complete_handler_schema_driven(monkeypatch):
    action_sink = AsyncMock()
    update_thought_status = MagicMock()
    update_task_status = MagicMock(return_value=True)
    get_task_by_id = MagicMock(return_value=Task(
        task_id="task1",
        description="desc",
        status=TaskStatus.ACTIVE,
        priority=0,
        created_at="now",
        updated_at="now",
        context={},
        outcome={},
    ))
    monkeypatch.setattr("ciris_engine.persistence.update_thought_status", update_thought_status)
    monkeypatch.setattr("ciris_engine.persistence.update_task_status", update_task_status)
    monkeypatch.setattr("ciris_engine.persistence.get_task_by_id", get_task_by_id)

    deps = ActionHandlerDependencies(action_sink=action_sink)
    handler = TaskCompleteHandler(deps)

    action_result = ActionSelectionResult(
        selected_action=HandlerActionType.TASK_COMPLETE,
        action_parameters={},
        rationale="r",
    )
    thought = Thought(**DEFAULT_THOUGHT_KWARGS)

    await handler.handle(action_result, thought, {"channel_id": "chan"})

    update_thought_status.assert_called_once()
    update_task_status.assert_called_once_with("task1", TaskStatus.COMPLETED)
    action_sink.send_message.assert_awaited()


@pytest.mark.asyncio
async def test_tool_handler_schema_driven(monkeypatch):
    action_sink = AsyncMock()
    update_status = MagicMock()
    add_thought = MagicMock()
    monkeypatch.setattr("ciris_engine.persistence.update_thought_status", update_status)
    monkeypatch.setattr("ciris_engine.persistence.add_thought", add_thought)

    ToolHandler._tool_registry = ToolRegistry()
    ToolHandler._tool_registry.register_tool("echo", {"dummy": True}, lambda **k: None)

    deps = ActionHandlerDependencies(action_sink=action_sink)
    handler = ToolHandler(deps)

    async def run_tool(name, args):
        await handler.register_tool_result(
            args["correlation_id"],
            ToolResult(tool_name=name, execution_status=ToolExecutionStatus.SUCCESS),
        )
    action_sink.run_tool.side_effect = run_tool

    params = ToolParams(name="echo", args={})
    action_result = ActionSelectionResult.model_construct(
        selected_action=HandlerActionType.TOOL,
        action_parameters=params,
        rationale="r",
    )
    thought = Thought(**DEFAULT_THOUGHT_KWARGS)

    await handler.handle(action_result, thought, {})

    action_sink.run_tool.assert_awaited()
    update_status.assert_called_once()
    add_thought.assert_called_once()
