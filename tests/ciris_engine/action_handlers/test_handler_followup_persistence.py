import os
import tempfile
import pytest
from datetime import datetime, timezone
from ciris_engine.persistence.db import initialize_database
from ciris_engine.persistence.thoughts import get_thoughts_by_task_id, add_thought, get_thought_by_id
from ciris_engine.persistence.tasks import add_task
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, Task
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, TaskStatus, HandlerActionType
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.action_params_v1 import (
    SpeakParams, RememberParams, ForgetParams, MemorizeParams, PonderParams, ObserveParams
)
from ciris_engine.action_handlers.speak_handler import SpeakHandler
from ciris_engine.action_handlers.remember_handler import RememberHandler
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
        task_id=task_id,
        description="desc",
        status=TaskStatus.PENDING,
        priority=0,
        created_at=now,
        updated_at=now
    )

def make_thought(thought_id, source_task_id, status=ThoughtStatus.PENDING):
    now = datetime.now(timezone.utc).isoformat()
    return Thought(
        thought_id=thought_id,
        source_task_id=source_task_id,
        thought_type="standard",
        status=status,
        created_at=now,
        updated_at=now,
        round_number=1,
        content="test content",
        context={},
        ponder_count=0,
        ponder_notes=None,
        parent_thought_id=None,
        final_action={}
    )

@pytest.mark.asyncio
@pytest.mark.parametrize("handler_cls,params,result_action,extra_setup", [
    (SpeakHandler, SpeakParams(content="hello", channel_id="c1"), HandlerActionType.SPEAK, None),
    (RememberHandler, RememberParams(query="q", scope="identity"), HandlerActionType.REMEMBER, None),
    (ForgetHandler, ForgetParams(key="k", scope="identity", reason="r"), HandlerActionType.FORGET, None),
    (MemorizeHandler, MemorizeParams(key="k", value="v", scope="identity"), HandlerActionType.MEMORIZE, None),
    (PonderHandler, PonderParams(questions=["q1", "q2"]), HandlerActionType.PONDER, None),
    (ObserveHandler, ObserveParams(active=False, channel_id="c1"), HandlerActionType.OBSERVE, None),
    (RejectHandler, {"reason": "bad"}, HandlerActionType.REJECT, None),
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
        deps.memory_service.remember = AsyncMock(return_value=MagicMock(status="OK", data="result"))
        deps.memory_service.forget = AsyncMock(return_value=MagicMock(status="OK"))
        deps.memory_service.memorize = AsyncMock(return_value=MagicMock(status="SAVED"))
        deps.action_sink = AsyncMock()
        deps.audit_service = MagicMock()
        deps.audit_service.log_action = AsyncMock()
        handler_mod = importlib.import_module(handler_cls.__module__)
        # Patch strategy: if module has 'persistence', patch it; else patch deps.persistence
        patch_module = hasattr(handler_mod, 'persistence')
        if patch_module:
            with patch.object(handler_mod.persistence, 'add_thought', side_effect=lambda t, db_path_=None: add_thought(t, db_path=db_path)), \
                 patch.object(handler_mod.persistence, 'update_thought_status', side_effect=lambda **kwargs: None):
                handler = handler_cls(deps)
                result = ActionSelectionResult(selected_action=result_action, action_parameters=params, rationale="r")
                dispatch_context = {"channel_id": "c1"}
                if extra_setup:
                    extra_setup(deps, thought, db_path)
                await handler.handle(result, thought, dispatch_context)
        else:
            deps.persistence = MagicMock()
            deps.persistence.add_thought = lambda t, db_path_=None: add_thought(t, db_path=db_path)
            deps.persistence.update_thought_status = lambda **kwargs: None
            handler = handler_cls(deps)
            result = ActionSelectionResult(selected_action=result_action, action_parameters=params, rationale="r")
            dispatch_context = {"channel_id": "c1"}
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
