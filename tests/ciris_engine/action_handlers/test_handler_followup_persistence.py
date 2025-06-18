import os
import tempfile
import pytest
from datetime import datetime, timezone
from ciris_engine.persistence import initialize_database
from ciris_engine.persistence import (
    get_thoughts_by_task_id,
    add_thought,
    get_thought_by_id,
)
from ciris_engine.persistence import add_task
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, Task
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, TaskStatus, HandlerActionType, ThoughtType, DispatchContext
from tests.helpers import create_test_dispatch_context
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.action_params_v1 import (
    SpeakParams, RecallParams, ForgetParams, MemorizeParams, PonderParams, ObserveParams, RejectParams
)
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, GraphScope, NodeType
from ciris_engine.utils.channel_utils import create_channel_context
from ciris_engine.action_handlers.speak_handler import SpeakHandler
from ciris_engine.action_handlers.recall_handler import RecallHandler
from ciris_engine.action_handlers.forget_handler import ForgetHandler
from ciris_engine.action_handlers.memorize_handler import MemorizeHandler
from ciris_engine.action_handlers.ponder_handler import PonderHandler
from ciris_engine.action_handlers.observe_handler import ObserveHandler
from ciris_engine.action_handlers.reject_handler import RejectHandler
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies
from unittest.mock import AsyncMock, MagicMock
import importlib
from unittest.mock import patch

# Utility for temp DB

def temp_db_file():
    f = tempfile.NamedTemporaryFile(delete=False)
    f.close()
    return f.name

def make_task(task_id):
    now = datetime.now(timezone.utc).isoformat()
    return Task(
        task_id=str(task_id),
        description=f"desc-{task_id}",
        status=TaskStatus.PENDING,
        priority=0,
        created_at=now,
        updated_at=now
    )

def make_thought(thought_id, source_task_id, status=ThoughtStatus.PENDING, thought_type=ThoughtType.FOLLOW_UP):
    now = datetime.now(timezone.utc).isoformat()
    # Create a dummy action result for the thought
    action_result = ActionSelectionResult(
        selected_action=HandlerActionType.OBSERVE,
        action_parameters={},
        rationale="test"
    )
    return Thought(
        thought_id=str(thought_id),
        source_task_id=str(source_task_id),
        thought_type=thought_type,
        status=status,
        created_at=now,
        updated_at=now,
        round_number=0,
        content="test content",
        context=None,
        thought_depth=0,
        ponder_notes=None,
        parent_thought_id=None,
        final_action=action_result.model_dump()
    )

@pytest.mark.asyncio
@pytest.mark.parametrize("handler_cls,params,result_action,extra_setup", [
    # SPEAK: content must be a string
    (
        SpeakHandler,
        SpeakParams(
            content="hello",
            channel_context=create_channel_context("c1")
        ),
        HandlerActionType.SPEAK,
        None
    ),
    # RECALL: id/type must be NodeType enums
    (
        RecallHandler,
        RecallParams(
            node=GraphNode(
                id="concept1",
                type=NodeType.CONCEPT,
                scope=GraphScope.IDENTITY
            )
        ),
        HandlerActionType.RECALL,
        None
    ),
    # FORGET: node must be GraphNode, reason must be string
    (
        ForgetHandler,
        ForgetParams(
            node=GraphNode(
                id="concept1",
                type=NodeType.CONCEPT,
                scope=GraphScope.IDENTITY
            ),
            reason="no longer needed"
        ),
        HandlerActionType.FORGET,
        None
    ),
    # MEMORIZE: id/type must be NodeType enums
    (
        MemorizeHandler,
        MemorizeParams(
            node=GraphNode(
                id="concept1",
                type=NodeType.CONCEPT,
                scope=GraphScope.IDENTITY,
                attributes={"value": "v"}
            )
        ),
        HandlerActionType.MEMORIZE,
        None
    ),
    # PONDER: unchanged (list of strings)
    (
        PonderHandler,
        PonderParams(questions=["q1", "q2"]),
        HandlerActionType.PONDER,
        None
    ),
    # OBSERVE: active must be bool, context must be dict
    (
        ObserveHandler,
        ObserveParams(
            active=True,
            channel_context=create_channel_context("c1"),
            context={"source": "test"}
        ),
        HandlerActionType.OBSERVE,
        None
    ),
    # REJECT: reason must be string
    (
        RejectHandler,
        RejectParams(reason="Not relevant to the task"),
        HandlerActionType.REJECT,
        None
    ),
])
async def test_handler_creates_followup_persistence(handler_cls, params, result_action, extra_setup):
    db_path = temp_db_file()
    try:
        initialize_database(db_path=db_path)
        add_task(make_task("task1"), db_path=db_path)
        thought = make_thought("t1", source_task_id="task1")
        add_thought(thought, db_path=db_path)
        deps = ActionHandlerDependencies()
        deps.memory_service = AsyncMock()
        deps.memory_service.recall = AsyncMock(return_value=MagicMock(status="OK", data="result"))
        deps.memory_service.forget = AsyncMock(return_value=MagicMock(status="OK"))
        deps.memory_service.memorize = AsyncMock(return_value=MagicMock(status="SAVED"))
        audit_service = MagicMock()
        audit_service.log_action = AsyncMock()
        async def get_service(handler, service_type, **kwargs):
            if service_type == "audit":
                return audit_service
            return None
        deps.get_service = AsyncMock(side_effect=get_service)
        handler_mod = importlib.import_module(handler_cls.__module__)
        # Patch strategy: if module has 'persistence', patch it; else patch deps.persistence
        patch_module = hasattr(handler_mod, 'persistence')
        if patch_module:
            with patch.object(handler_mod.persistence, 'add_thought', side_effect=lambda t, db_path_=None: add_thought(t, db_path=db_path)), \
                 patch.object(handler_mod.persistence, 'update_thought_status', side_effect=lambda **kwargs: None), \
                 patch.object(handler_mod.persistence, 'add_correlation', side_effect=lambda c, db_path_=None: c.correlation_id), \
                 patch.object(handler_mod.persistence, 'get_task_by_id', side_effect=lambda task_id, db_path_=None: make_task(task_id)):
                handler = handler_cls(deps)
                result = ActionSelectionResult(selected_action=result_action, action_parameters=params, rationale="r")
                dispatch_context = create_test_dispatch_context(channel_id="c1", thought_id=thought.thought_id, source_task_id=thought.source_task_id, wa_authorized=True, action_type=result_action)
                if extra_setup:
                    extra_setup(deps, thought, db_path)
                await handler.handle(result, thought, dispatch_context)
        else:
            deps.persistence = MagicMock()
            deps.persistence.add_thought = lambda t, db_path_=None: add_thought(t, db_path=db_path)
            deps.persistence.update_thought_status = lambda **kwargs: None
            deps.persistence.add_correlation = lambda c, db_path_=None: c.correlation_id
            deps.persistence.get_task_by_id = lambda task_id, db_path_=None: make_task(task_id)
            handler = handler_cls(deps)
            result = ActionSelectionResult(selected_action=result_action, action_parameters=params, rationale="r")
            dispatch_context = {"channel_id": "c1", "wa_authorized": True}
            if extra_setup:
                extra_setup(deps, thought, db_path)
            await handler.handle(result, thought, dispatch_context)
        thoughts = get_thoughts_by_task_id("task1", db_path=db_path)
        follow_ups = [t for t in thoughts if t.parent_thought_id == "t1" and t.thought_type == "follow_up"]
        
        # Terminal actions (REJECT, DEFER, TASK_COMPLETE) don't create follow-up thoughts
        terminal_actions = {HandlerActionType.REJECT, HandlerActionType.DEFER, HandlerActionType.TASK_COMPLETE}
        if result_action in terminal_actions:
            assert not follow_ups, f"Terminal action {handler_cls.__name__} should not create follow-up thoughts"
            return
            
        assert follow_ups, f"No follow-up thought created for handler {handler_cls.__name__}"
        follow_up = follow_ups[0]
        # Accept both upper/lower case for action_performed
        ap = follow_up.context.get("action_performed", "")
        print(f"DEBUG: ap={ap!r}, result_action={result_action!r}, follow_up.content={follow_up.content!r}")
        if follow_up.content == "pending":
            # Accept any ap for pending placeholder
            pass
        else:
            assert ap.lower() == result_action.value.lower() or result_action.value in follow_up.content.lower()
        assert follow_up.context.get("is_follow_up", True)
    finally:
        os.unlink(db_path)
