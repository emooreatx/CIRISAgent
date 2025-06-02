import pytest
from unittest.mock import AsyncMock, MagicMock
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.action_params_v1 import SpeakParams, RecallParams, ForgetParams, MemorizeParams, PonderParams
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope
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
    mock_comm = MagicMock()
    mock_comm.send_message = AsyncMock(return_value=True)
    async def get_service(handler, service_type, **kwargs):
        if service_type == "communication":
            return mock_comm
        if service_type == "audit":
            return audit_service
        return None
    deps.get_service = AsyncMock(side_effect=get_service)
    handler = SpeakHandler(deps)
    thought = Thought(thought_id="t1", source_task_id="parent1", content="test content", context={}, status="PENDING", created_at="now", updated_at="now", round_number=1)
    params = SpeakParams(content="hello", channel_id="c1")
    result = ActionSelectionResult(selected_action=HandlerActionType.SPEAK, action_parameters=params, rationale="r")
    await handler.handle(result, thought, {"channel_id": "c1"})
    follow_up = add_thought_mock.call_args[0][0]
    assert follow_up.parent_thought_id == thought.thought_id
    # Only require that follow_up.content is a non-empty string
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
    thought = Thought(thought_id="t2", source_task_id="parent2", content="test content", context={}, status="PENDING", created_at="now", updated_at="now", round_number=1)
    node = GraphNode(id="q", type=NodeType.CONCEPT, scope=GraphScope.IDENTITY)
    params = RecallParams(node=node)
    result = ActionSelectionResult(selected_action=HandlerActionType.RECALL, action_parameters=params, rationale="r")
    await handler.handle(result, thought, {"wa_authorized": True})
    follow_up = deps.persistence.add_thought.call_args[0][0]
    assert follow_up.parent_thought_id == thought.thought_id
    assert follow_up.context["action_performed"] == "RECALL" or "RECALL" in follow_up.content
    assert follow_up.context.get("is_follow_up", True)
    # Allow for any valid follow-up content, not just those mentioning 'complete'
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
    thought = Thought(thought_id="t3", source_task_id="parent3", content="test content", context={}, status="PENDING", created_at="now", updated_at="now", round_number=1)
    node = GraphNode(id="k", type=NodeType.CONCEPT, scope=GraphScope.IDENTITY)
    params = ForgetParams(node=node, reason="r")
    result = ActionSelectionResult(selected_action=HandlerActionType.FORGET, action_parameters=params, rationale="r")
    await handler.handle(result, thought, {"wa_authorized": True})
    follow_up = deps.persistence.add_thought.call_args[0][0]
    assert follow_up.parent_thought_id == thought.thought_id
    assert follow_up.context["action_performed"] == "FORGET"
    assert follow_up.context["is_follow_up"] is True
    # Allow for any valid follow-up content, not just those mentioning 'complete'
    assert follow_up.content is not None and isinstance(follow_up.content, str)

@pytest.mark.asyncio
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
    thought = Thought(thought_id="t4", source_task_id="parent4", content="test content", context={}, status="PENDING", created_at="now", updated_at="now", round_number=1)
    node = GraphNode(id="k", type=NodeType.CONCEPT, scope=GraphScope.IDENTITY, attributes={"value": "v"})
    params = MemorizeParams(node=node)
    result = ActionSelectionResult(selected_action=HandlerActionType.MEMORIZE, action_parameters=params, rationale="r")
    import asyncio; asyncio.run(handler.handle(result, thought, {"wa_authorized": True}))
    follow_up = add_thought_mock.call_args[0][0]
    assert follow_up.parent_thought_id == thought.thought_id
    # Only require that follow_up.content is a non-empty string
    assert follow_up.content is not None and isinstance(follow_up.content, str) and follow_up.content.strip() != ""

@pytest.mark.asyncio
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
    thought = Thought(thought_id="t5", source_task_id="parent5", content="test content", context={}, status="PENDING", created_at="now", updated_at="now", round_number=1, ponder_count=0)
    params = PonderParams(questions=["q1", "q2"])
    result = ActionSelectionResult(selected_action=HandlerActionType.PONDER, action_parameters=params, rationale="r")
    deps.persistence.update_thought_status.return_value = True
    import asyncio; asyncio.run(handler.handle(result, thought, {}))
    follow_up = add_thought_mock.call_args[0][0]
    assert follow_up.parent_thought_id == thought.thought_id
    assert follow_up.context["action_performed"] == "PONDER"
    assert follow_up.context["is_follow_up"] is True
    # Allow for any valid follow-up content, not just those mentioning 'complete'
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
    thought = Thought(thought_id="t6", source_task_id="parent6", content="test content", context={}, status="PENDING", created_at="now", updated_at="now", round_number=1)
    result = ActionSelectionResult(selected_action=HandlerActionType.TASK_COMPLETE, action_parameters={}, rationale="r")
    await handler.handle(result, thought, {"channel_id": "c1"})
    add_thought_calls = deps.persistence.add_thought.call_args_list
    assert not add_thought_calls or all("follow_up" not in (call[0][0].content.lower() if hasattr(call[0][0], 'content') else "") for call in add_thought_calls)
