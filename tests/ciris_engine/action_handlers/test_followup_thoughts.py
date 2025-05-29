import pytest
from unittest.mock import AsyncMock, MagicMock
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.action_params_v1 import SpeakParams, RememberParams, ForgetParams, MemorizeParams, PonderParams
from ciris_engine.action_handlers.speak_handler import SpeakHandler
from ciris_engine.action_handlers.remember_handler import RememberHandler
from ciris_engine.action_handlers.forget_handler import ForgetHandler
from ciris_engine.action_handlers.memorize_handler import MemorizeHandler
from ciris_engine.action_handlers.ponder_handler import PonderHandler
from ciris_engine.action_handlers.task_complete_handler import TaskCompleteHandler
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies

@pytest.mark.asyncio
async def test_speak_handler_creates_followup():
    deps = MagicMock()
    deps.action_sink = AsyncMock()
    deps.persistence = MagicMock()
    deps.audit_service = MagicMock()
    deps.audit_service.log_action = AsyncMock()
    handler = SpeakHandler(deps)
    thought = Thought(thought_id="t1", source_task_id="parent1", content="test content", context={}, status="PENDING", created_at="now", updated_at="now", round_number=1)
    params = SpeakParams(content="hello", channel_id="c1")
    result = ActionSelectionResult(selected_action=HandlerActionType.SPEAK, action_parameters=params, rationale="r")
    await handler.handle(result, thought, {"channel_id": "c1"})
    follow_up = deps.persistence.add_thought.call_args[0][0]
    assert follow_up.parent_thought_id == thought.thought_id
    assert follow_up.context["action_performed"] == HandlerActionType.SPEAK.value
    assert follow_up.context["is_follow_up"] is True or "follow_up" in follow_up.content.lower()
    assert "COMPLETE_TASK" in follow_up.content or "complete" in follow_up.content.lower()

@pytest.mark.asyncio
async def test_remember_handler_creates_followup():
    deps = MagicMock()
    deps.memory_service = AsyncMock()
    deps.memory_service.remember = AsyncMock(return_value=MagicMock(status="OK", data="result"))
    deps.persistence = MagicMock()
    deps.audit_service = MagicMock()
    deps.audit_service.log_action = AsyncMock()
    handler = RememberHandler(deps)
    thought = Thought(thought_id="t2", source_task_id="parent2", content="test content", context={}, status="PENDING", created_at="now", updated_at="now", round_number=1)
    params = RememberParams(query="q", scope="identity")
    result = ActionSelectionResult(selected_action=HandlerActionType.REMEMBER, action_parameters=params, rationale="r")
    await handler.handle(result, thought, {})
    follow_up = deps.persistence.add_thought.call_args[0][0]
    assert follow_up.parent_thought_id == thought.thought_id
    assert follow_up.context["action_performed"] == "REMEMBER" or "REMEMBER" in follow_up.content
    assert follow_up.context.get("is_follow_up", True)
    assert "COMPLETE_TASK" in follow_up.content or "complete" in follow_up.content.lower()

@pytest.mark.asyncio
async def test_forget_handler_creates_followup():
    deps = MagicMock()
    deps.memory_service = AsyncMock()
    deps.memory_service.forget = AsyncMock(return_value=MagicMock(status="OK"))
    deps.persistence = MagicMock()
    deps.audit_service = MagicMock()
    deps.audit_service.log_action = AsyncMock()
    handler = ForgetHandler(deps)
    thought = Thought(thought_id="t3", source_task_id="parent3", content="test content", context={}, status="PENDING", created_at="now", updated_at="now", round_number=1)
    params = ForgetParams(key="k", scope="identity", reason="r")
    result = ActionSelectionResult(selected_action=HandlerActionType.FORGET, action_parameters=params, rationale="r")
    await handler.handle(result, thought, {})
    follow_up = deps.persistence.add_thought.call_args[0][0]
    assert follow_up.parent_thought_id == thought.thought_id
    assert follow_up.context["action_performed"] == "FORGET"
    assert follow_up.context["is_follow_up"] is True
    assert "COMPLETE_TASK" in follow_up.content or "complete" in follow_up.content.lower()

@pytest.mark.asyncio
async def test_memorize_handler_creates_followup():
    deps = MagicMock()
    deps.memory_service = AsyncMock()
    deps.memory_service.memorize = AsyncMock(return_value=MagicMock(status="SAVED"))
    deps.persistence = MagicMock()
    deps.audit_service = MagicMock()
    deps.audit_service.log_action = AsyncMock()
    handler = MemorizeHandler(deps)
    thought = Thought(thought_id="t4", source_task_id="parent4", content="test content", context={}, status="PENDING", created_at="now", updated_at="now", round_number=1)
    params = MemorizeParams(key="k", value="v", scope="identity")
    result = ActionSelectionResult(selected_action=HandlerActionType.MEMORIZE, action_parameters=params, rationale="r")
    await handler.handle(result, thought, {})
    follow_up = deps.persistence.add_thought.call_args[0][0]
    assert follow_up.parent_thought_id == thought.thought_id
    assert follow_up.context["action_performed"] == "MEMORIZE"
    assert follow_up.context["is_follow_up"] is True
    assert "COMPLETE_TASK" in follow_up.content or "complete" in follow_up.content.lower()

@pytest.mark.asyncio
async def test_ponder_handler_creates_followup():
    deps = MagicMock()
    deps.persistence = MagicMock()
    deps.audit_service = MagicMock()
    deps.audit_service.log_action = AsyncMock()
    handler = PonderHandler(deps)
    thought = Thought(thought_id="t5", source_task_id="parent5", content="test content", context={}, status="PENDING", created_at="now", updated_at="now", round_number=1, ponder_count=0)
    params = PonderParams(questions=["q1", "q2"])
    result = ActionSelectionResult(selected_action=HandlerActionType.PONDER, action_parameters=params, rationale="r")
    deps.persistence.update_thought_status.return_value = True
    await handler.handle(result, thought, {})
    follow_up = deps.persistence.add_thought.call_args[0][0]
    assert follow_up.parent_thought_id == thought.thought_id
    assert follow_up.context["action_performed"] == "PONDER"
    assert follow_up.context["is_follow_up"] is True
    assert "COMPLETE_TASK" in follow_up.content or "complete" in follow_up.content.lower()

@pytest.mark.asyncio
async def test_task_complete_handler_no_followup():
    deps = MagicMock()
    deps.persistence = MagicMock()
    deps.action_sink = AsyncMock()
    deps.audit_service = MagicMock()
    deps.audit_service.log_action = AsyncMock()
    handler = TaskCompleteHandler(deps)
    thought = Thought(thought_id="t6", source_task_id="parent6", content="test content", context={}, status="PENDING", created_at="now", updated_at="now", round_number=1)
    result = ActionSelectionResult(selected_action=HandlerActionType.TASK_COMPLETE, action_parameters={}, rationale="r")
    await handler.handle(result, thought, {"channel_id": "c1"})
    add_thought_calls = deps.persistence.add_thought.call_args_list
    assert not add_thought_calls or all("follow_up" not in (call[0][0].content.lower() if hasattr(call[0][0], 'content') else "") for call in add_thought_calls)
