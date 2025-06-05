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
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, TaskStatus, HandlerActionType
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.action_params_v1 import (
    SpeakParams, RecallParams, ForgetParams, MemorizeParams, PonderParams, ObserveParams
)
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, GraphScope, NodeType
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
    # Use TaskStatus enums for all required fields
    return Task(
        task_id=TaskStatus.PENDING,
        description=TaskStatus.PENDING,
        status=TaskStatus.PENDING,
        priority=TaskStatus.PENDING,
        created_at=TaskStatus.PENDING,
        updated_at=TaskStatus.PENDING
    )

def make_thought(thought_id, source_task_id, status=ThoughtStatus.PENDING):
    # Use ThoughtStatus enums for all required fields
    return Thought(
        thought_id=ThoughtStatus.PENDING,
        source_task_id=ThoughtStatus.PENDING,
        thought_type=ThoughtStatus.PENDING,
        status=status,
        created_at=ThoughtStatus.PENDING,
        updated_at=ThoughtStatus.PENDING,
        round_number=ThoughtStatus.PENDING,
        content=ThoughtStatus.PENDING,
        context={},
        ponder_count=ThoughtStatus.PENDING,
        ponder_notes=None,
        parent_thought_id=None,
        final_action={}
    )

@pytest.mark.asyncio
@pytest.mark.parametrize("handler_cls,params,result_action,extra_setup", [
    # SPEAK: content must be a GraphNode, not a string
    (
        SpeakHandler,
        SpeakParams(
            content=GraphNode(
                id=NodeType.AGENT,
                type=NodeType.AGENT,
                scope=GraphScope.LOCAL,
                attributes={"text": "hello"}
            ),
            channel_id="c1"
        ),
        HandlerActionType.SPEAK,
        None
    ),
    # RECALL: id/type must be NodeType enums
    (
        RecallHandler,
        RecallParams(
            node=GraphNode(
                id=NodeType.CONCEPT,
                type=NodeType.CONCEPT,
                scope=GraphScope.IDENTITY
            )
        ),
        HandlerActionType.RECALL,
        None
    ),
    # FORGET: id/type must be NodeType enums, reason must be GraphNode
    (
        ForgetHandler,
        ForgetParams(
            node=GraphNode(
                id=NodeType.CONCEPT,
                type=NodeType.CONCEPT,
                scope=GraphScope.IDENTITY
            ),
            reason=GraphNode(
                id=NodeType.USER,
                type=NodeType.USER,
                scope=GraphScope.LOCAL,
                attributes={"reason": "r"}
            )
        ),
        HandlerActionType.FORGET,
        None
    ),
    # MEMORIZE: id/type must be NodeType enums
    (
        MemorizeHandler,
        MemorizeParams(
            node=GraphNode(
                id=NodeType.CONCEPT,
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
    # OBSERVE: active/context must be GraphNode
    (
        ObserveHandler,
        ObserveParams(
            active=GraphNode(
                id=NodeType.CHANNEL,
                type=NodeType.CHANNEL,
                scope=GraphScope.LOCAL
            ),
            channel_id="c1",
            context=GraphNode(
                id=NodeType.AGENT,
                type=NodeType.AGENT,
                scope=GraphScope.LOCAL
            )
        ),
        HandlerActionType.OBSERVE,
        None
    ),
    # REJECT: reason must be GraphNode
    (
        RejectHandler,
        {"reason": GraphNode(
            id=NodeType.USER,
            type=NodeType.USER,
            scope=GraphScope.LOCAL,
            attributes={"reason": "bad"}
        )},
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
                 patch.object(handler_mod.persistence, 'update_thought_status', side_effect=lambda **kwargs: None):
                handler = handler_cls(deps)
                result = ActionSelectionResult(selected_action=result_action, action_parameters=params, rationale=MemorizeParams(node=GraphNode(id=NodeType.USER, type=NodeType.USER, scope=GraphScope.IDENTITY)))
                dispatch_context = {"channel_id": "c1", "wa_authorized": True}
                if extra_setup:
                    extra_setup(deps, thought, db_path)
                await handler.handle(result, thought, dispatch_context)
        else:
            deps.persistence = MagicMock()
            deps.persistence.add_thought = lambda t, db_path_=None: add_thought(t, db_path=db_path)
            deps.persistence.update_thought_status = lambda **kwargs: None
            handler = handler_cls(deps)
            result = ActionSelectionResult(selected_action=result_action, action_parameters=params, rationale=MemorizeParams(node=GraphNode(id=NodeType.USER, type=NodeType.USER, scope=GraphScope.IDENTITY)))
            dispatch_context = {"channel_id": "c1", "wa_authorized": True}
            if extra_setup:
                extra_setup(deps, thought, db_path)
            await handler.handle(result, thought, dispatch_context)
        thoughts = get_thoughts_by_task_id("task1", db_path=db_path)
        follow_ups = [t for t in thoughts if t.parent_thought_id == "t1" and t.thought_type == "follow_up"]
        assert follow_ups, f"No follow-up thought created for handler {handler_cls.__name__}"
        follow_up = follow_ups[0]
        # Accept both upper/lower case for action_performed
        ap = follow_up.context.get("action_performed", "")
        assert ap.lower() == result_action.value.lower() or result_action.value in follow_up.content.lower()
        assert follow_up.context.get("is_follow_up", True)
    finally:
        os.unlink(db_path)
