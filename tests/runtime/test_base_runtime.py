import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ciris_engine.runtime.base_runtime import BaseRuntime, BaseIOAdapter, IncomingMessage
from ciris_engine import persistence
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.action_handlers.action_dispatcher import ActionDispatcher
from ciris_engine.schemas.agent_core_schemas_v1 import (
    Thought,
    ActionSelectionPDMAResult,
    SpeakParams,
)
from ciris_engine.action_handlers.speak_handler import SpeakHandler
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies
from types import SimpleNamespace

class DummyAdapter(BaseIOAdapter):
    def __init__(self):
        self.outputs = []
    async def start(self):
        pass
    async def stop(self):
        pass
    async def fetch_inputs(self):
        return []
    async def send_output(self, target, content):
        self.outputs.append((target, content))

@pytest.mark.asyncio
async def test_create_task_if_new(tmp_path, monkeypatch):
    db_file = tmp_path / "db.sqlite"
    monkeypatch.setattr(persistence, "get_sqlite_db_full_path", lambda: str(db_file))
    persistence.initialize_database()

    runtime = BaseRuntime(DummyAdapter(), "ciris_profiles/student.yaml", ActionDispatcher({}))

    created = await runtime._create_task_if_new("1", "hi", {"origin_service": "discord"})
    created_again = await runtime._create_task_if_new("1", "hi", {"origin_service": "discord"})

    assert created is True
    assert created_again is False

@pytest.mark.asyncio
async def test_dream_action_filter_blocks(mocker):
    svc = SimpleNamespace(send_message=mocker.AsyncMock())
    handler = SpeakHandler(ActionHandlerDependencies(action_sink=svc))
    dispatcher = ActionDispatcher({HandlerActionType.SPEAK: handler})
    runtime = BaseRuntime(DummyAdapter(), "ciris_profiles/student.yaml", dispatcher)

    with patch.object(persistence, "add_thought", lambda t: t), patch.object(persistence, "update_thought_status", lambda **k: None):
        result = ActionSelectionPDMAResult(
            context_summary_for_action_selection="c",
            action_alignment_check={},
            selected_handler_action=HandlerActionType.SPEAK,
            action_parameters=SpeakParams(content="x"),
            action_selection_rationale="r",
            monitoring_for_selected_action="m",
        )
        await runtime.dispatcher.dispatch(result, Thought(thought_id="t", source_task_id="task", created_at="", updated_at="", round_created=0, content=""), {"channel_id": "1"})
    svc.send_message.assert_awaited_once()

    svc.send_message.reset_mock()
    runtime.dreaming = True
    runtime.dispatcher.action_filter = runtime._dream_action_filter
    with patch.object(persistence, "add_thought", lambda t: t), patch.object(persistence, "update_thought_status", lambda **k: None):
        result2 = ActionSelectionPDMAResult(
            context_summary_for_action_selection="c",
            action_alignment_check={},
            selected_handler_action=HandlerActionType.SPEAK,
            action_parameters=SpeakParams(content="x"),
            action_selection_rationale="r",
            monitoring_for_selected_action="m",
        )
        await runtime.dispatcher.dispatch(result2, Thought(thought_id="t2", source_task_id="task", created_at="", updated_at="", round_created=0, content=""), {"channel_id": "1"})
    svc.send_message.assert_not_awaited()

@pytest.mark.asyncio
async def test_dream_protocol_emits_snore(mocker):
    adapter = DummyAdapter()
    dispatcher = ActionDispatcher({})
    runtime = BaseRuntime(adapter, "ciris_profiles/student.yaml", dispatcher, snore_channel_id="c")
    log_mock = mocker.AsyncMock()
    runtime.audit_service.log_action = log_mock
    await runtime.run_dream(duration=0.1, pulse_interval=0.05)

    assert any("snore" in o[1] for o in adapter.outputs)
    assert any("Dream ended" in o[1] for o in adapter.outputs)
    assert log_mock.await_count >= 2

