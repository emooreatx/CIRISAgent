import pytest
from unittest.mock import AsyncMock, MagicMock
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import SpeakParams, RecallParams, ForgetParams, PonderParams, MemorizeParams
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.graph_schemas_v1 import NodeType, GraphScope, GraphNode
from ciris_engine.action_handlers.speak_handler import SpeakHandler
from ciris_engine.action_handlers.recall_handler import RecallHandler
from ciris_engine.action_handlers.forget_handler import ForgetHandler
from ciris_engine.action_handlers.memorize_handler import MemorizeHandler
from ciris_engine.action_handlers.ponder_handler import PonderHandler
from ciris_engine.action_handlers.task_complete_handler import TaskCompleteHandler
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies

@pytest.mark.asyncio
async def test_speak_handler_creates_followup(monkeypatch):
    add_thought_mock = MagicMock()
    monkeypatch.setattr('ciris_engine.action_handlers.speak_handler.persistence.add_thought', add_thought_mock)
    deps = MagicMock()
    deps.persistence = MagicMock()
    deps.persistence.add_thought = add_thought_mock
    audit_service = MagicMock()
    audit_service.log_action = AsyncMock()
    deps.get_service = AsyncMock(return_value=audit_service)
    handler = SpeakHandler(deps)
    base_ctx = {"channel_id": "orig", "custom": "foo"}
    thought = Thought(
        thought_id=ThoughtStatus.PENDING,
        source_task_id=ThoughtStatus.PENDING,
        thought_type=ThoughtStatus.PENDING,
        status=ThoughtStatus.PENDING,
        created_at=ThoughtStatus.PENDING,
        updated_at=ThoughtStatus.PENDING,
        round_number=ThoughtStatus.PENDING,
        content=ThoughtStatus.PENDING,
        context=base_ctx,
        ponder_count=ThoughtStatus.PENDING,
        ponder_notes=None,
        parent_thought_id=None,
        final_action={},
    )
    params = SpeakParams(content=GraphNode(id=NodeType.USER, type=NodeType.USER, scope=GraphScope.IDENTITY), channel_id="c1")
    result = ActionSelectionResult(selected_action=HandlerActionType.SPEAK, action_parameters=params, rationale=MemorizeParams(node=GraphNode(id=NodeType.USER, type=NodeType.USER, scope=GraphScope.IDENTITY)))
    await handler.handle(result, thought, {"channel_id": "c1"})
    follow_up = add_thought_mock.call_args[0][0]
    assert follow_up.parent_thought_id == thought.thought_id
    for k, v in base_ctx.items():
        assert follow_up.context.get(k) == v
    assert follow_up.content is not None and isinstance(follow_up.content, str) and follow_up.content.strip() != ""

@pytest.mark.asyncio
async def test_recall_handler_creates_followup():
    memory_service = AsyncMock()
    memory_service.recall = AsyncMock(return_value=MagicMock(status="OK", data="result"))
    deps = ActionHandlerDependencies()
    deps.persistence = MagicMock()
    audit_service = MagicMock()
    audit_service.log_action = AsyncMock()
    async def get_service(handler, service_type, **kwargs):
        if service_type == "memory":
            return memory_service
        if service_type == "audit":
            return audit_service
        return None
    deps.get_service = AsyncMock(side_effect=get_service)
    handler = RecallHandler(deps)
    base_ctx = {"channel_id": "orig", "custom": "foo"}
    thought = Thought(
        thought_id=ThoughtStatus.PENDING,
        source_task_id=ThoughtStatus.PENDING,
        thought_type=ThoughtStatus.PENDING,
        status=ThoughtStatus.PENDING,
        created_at=ThoughtStatus.PENDING,
        updated_at=ThoughtStatus.PENDING,
        round_number=ThoughtStatus.PENDING,
        content=ThoughtStatus.PENDING,
        context=base_ctx,
        ponder_count=ThoughtStatus.PENDING,
        ponder_notes=None,
        parent_thought_id=None,
        final_action={},
    )
    node = GraphNode(id=NodeType.CONCEPT, type=NodeType.CONCEPT, scope=GraphScope.IDENTITY)
    params = RecallParams(node=node)
    result = ActionSelectionResult(selected_action=HandlerActionType.RECALL, action_parameters=params, rationale=MemorizeParams(node=node))
    await handler.handle(result, thought, {"wa_authorized": True})
    follow_up = deps.persistence.add_thought.call_args[0][0]
    assert follow_up.parent_thought_id == thought.thought_id
    for k, v in base_ctx.items():
        assert follow_up.context.get(k) == v
    assert follow_up.context["action_performed"] == "RECALL" or "RECALL" in follow_up.content
    assert follow_up.context.get("is_follow_up", True)
    assert follow_up.content is not None and isinstance(follow_up.content, str)

@pytest.mark.asyncio
async def test_forget_handler_creates_followup():
    memory_service = AsyncMock()
    memory_service.forget = AsyncMock(return_value=MagicMock(status="OK"))
    deps = ActionHandlerDependencies()
    deps.persistence = MagicMock()
    audit_service = MagicMock()
    audit_service.log_action = AsyncMock()
    async def get_service(handler, service_type, **kwargs):
        if service_type == "memory":
            return memory_service
        if service_type == "audit":
            return audit_service
        return None
    deps.get_service = AsyncMock(side_effect=get_service)
    handler = ForgetHandler(deps)
    base_ctx = {"channel_id": "orig", "custom": "foo"}
    thought = Thought(
        thought_id=ThoughtStatus.PENDING,
        source_task_id=ThoughtStatus.PENDING,
        thought_type=ThoughtStatus.PENDING,
        status=ThoughtStatus.PENDING,
        created_at=ThoughtStatus.PENDING,
        updated_at=ThoughtStatus.PENDING,
        round_number=ThoughtStatus.PENDING,
        content=ThoughtStatus.PENDING,
        context=base_ctx,
        ponder_count=ThoughtStatus.PENDING,
        ponder_notes=None,
        parent_thought_id=None,
        final_action={},
    )
    node = GraphNode(id=NodeType.CONCEPT, type=NodeType.CONCEPT, scope=GraphScope.IDENTITY)
    params = ForgetParams(node=node, reason=GraphNode(id=NodeType.USER, type=NodeType.USER, scope=GraphScope.LOCAL))
    result = ActionSelectionResult(selected_action=HandlerActionType.FORGET, action_parameters=params, rationale=MemorizeParams(node=node))
    await handler.handle(result, thought, {"wa_authorized": True})
    follow_up = deps.persistence.add_thought.call_args[0][0]
    assert follow_up.parent_thought_id == thought.thought_id
    for k, v in base_ctx.items():
        assert follow_up.context.get(k) == v
    assert follow_up.context["action_performed"] == "FORGET"
    assert follow_up.context["is_follow_up"] is True
    assert follow_up.content is not None and isinstance(follow_up.content, str)

def test_memorize_handler_creates_followup(monkeypatch):
    add_thought_mock = MagicMock()
    monkeypatch.setattr('ciris_engine.action_handlers.memorize_handler.persistence.add_thought', add_thought_mock)
    memory_service = AsyncMock()
    memory_service.memorize = AsyncMock(return_value=MagicMock(status="SAVED"))
    deps = ActionHandlerDependencies()
    deps.persistence = MagicMock()
    deps.persistence.add_thought = add_thought_mock
    audit_service = MagicMock()
    audit_service.log_action = AsyncMock()
    async def get_service(handler, service_type, **kwargs):
        if service_type == "memory":
            return memory_service
        if service_type == "audit":
            return audit_service
        return None
    deps.get_service = AsyncMock(side_effect=get_service)
    handler = MemorizeHandler(deps)
    base_ctx = {"channel_id": "orig", "custom": "foo"}
    thought = Thought(
        thought_id=ThoughtStatus.PENDING,
        source_task_id=ThoughtStatus.PENDING,
        thought_type=ThoughtStatus.PENDING,
        status=ThoughtStatus.PENDING,
        created_at=ThoughtStatus.PENDING,
        updated_at=ThoughtStatus.PENDING,
        round_number=ThoughtStatus.PENDING,
        content=ThoughtStatus.PENDING,
        context=base_ctx,
        ponder_count=ThoughtStatus.PENDING,
        ponder_notes=None,
        parent_thought_id=None,
        final_action={},
    )
    node = GraphNode(id=NodeType.CONCEPT, type=NodeType.CONCEPT, scope=GraphScope.IDENTITY, attributes={"value": "v"})
    params = MemorizeParams(node=node)
    result = ActionSelectionResult(selected_action=HandlerActionType.MEMORIZE, action_parameters=params, rationale=MemorizeParams(node=node))
    import asyncio; asyncio.run(handler.handle(result, thought, {"wa_authorized": True}))
    follow_up = add_thought_mock.call_args[0][0]
    assert follow_up.parent_thought_id == thought.thought_id
    for k, v in base_ctx.items():
        assert follow_up.context.get(k) == v
    assert follow_up.content is not None and isinstance(follow_up.content, str) and follow_up.content.strip() != ""

def test_ponder_handler_creates_followup(monkeypatch):
    add_thought_mock = MagicMock()
    monkeypatch.setattr('ciris_engine.action_handlers.ponder_handler.persistence.add_thought', add_thought_mock)
    deps = MagicMock()
    deps.persistence = MagicMock()
    deps.persistence.add_thought = add_thought_mock
    audit_service = MagicMock()
    audit_service.log_action = AsyncMock()
    async def get_service(handler, service_type, **kwargs):
        if service_type == "audit":
            return audit_service
        return None
    deps.get_service = AsyncMock(side_effect=get_service)
    handler = PonderHandler(deps)
    base_ctx = {"channel_id": "orig", "custom": "foo"}
    thought = Thought(
        thought_id=ThoughtStatus.PENDING,
        source_task_id=ThoughtStatus.PENDING,
        thought_type=ThoughtStatus.PENDING,
        status=ThoughtStatus.PENDING,
        created_at=ThoughtStatus.PENDING,
        updated_at=ThoughtStatus.PENDING,
        round_number=ThoughtStatus.PENDING,
        content=ThoughtStatus.PENDING,
        context=base_ctx,
        ponder_count=ThoughtStatus.PENDING,
        ponder_notes=None,
        parent_thought_id=None,
        final_action={},
    )
    params = PonderParams(questions=["q1", "q2"])
    result = ActionSelectionResult(selected_action=HandlerActionType.PONDER, action_parameters=params, rationale="r")
    deps.persistence.update_thought_status.return_value = True
    import asyncio; asyncio.run(handler.handle(result, thought, {}))
    follow_up = add_thought_mock.call_args[0][0]
    assert follow_up.parent_thought_id == thought.thought_id
    for k, v in base_ctx.items():
        assert follow_up.context.get(k) == v
    assert follow_up.context["action_performed"] == "PONDER"
    assert follow_up.context["is_follow_up"] is True
    assert follow_up.content is not None and isinstance(follow_up.content, str)

@pytest.mark.asyncio
async def test_task_complete_handler_no_followup():
    deps = MagicMock()
    deps.persistence = MagicMock()
    audit_service = MagicMock()
    audit_service.log_action = AsyncMock()
    async def get_service(handler, service_type, **kwargs):
        if service_type == "audit":
            return audit_service
        return None
    deps.get_service = AsyncMock(side_effect=get_service)
    handler = TaskCompleteHandler(deps)
    base_ctx = {"channel_id": "orig", "custom": "foo"}
    thought = Thought(
        thought_id=ThoughtStatus.PENDING,
        source_task_id=ThoughtStatus.PENDING,
        thought_type=ThoughtStatus.PENDING,
        status=ThoughtStatus.PENDING,
        created_at=ThoughtStatus.PENDING,
        updated_at=ThoughtStatus.PENDING,
        round_number=ThoughtStatus.PENDING,
        content=ThoughtStatus.PENDING,
        context=base_ctx,
        ponder_count=ThoughtStatus.PENDING,
        ponder_notes=None,
        parent_thought_id=None,
        final_action={},
    )
    result = ActionSelectionResult(selected_action=HandlerActionType.TASK_COMPLETE, action_parameters={}, rationale="r")
    await handler.handle(result, thought, {"channel_id": "c1"})
    add_thought_calls = deps.persistence.add_thought.call_args_list
    assert not add_thought_calls or all("follow_up" not in (call[0][0].content.lower() if hasattr(call[0][0], 'content') else "") for call in add_thought_calls)
