import asyncio
import json
from pathlib import Path

import pytest

from ciris_engine.runtime.base_runtime import BaseRuntime, BaseIOAdapter, IncomingMessage
from ciris_engine.core import persistence
from ciris_engine.core.foundational_schemas import HandlerActionType
from ciris_engine.core.agent_core_schemas import Thought

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

    runtime = BaseRuntime(DummyAdapter(), "ciris_profiles/student.yaml")

    created = await runtime._create_task_if_new("1", "hi", {"origin_service": "discord"})
    created_again = await runtime._create_task_if_new("1", "hi", {"origin_service": "discord"})

    assert created is True
    assert created_again is False

@pytest.mark.asyncio
async def test_dream_action_filter_blocks(mocker):
    runtime = BaseRuntime(DummyAdapter(), "ciris_profiles/student.yaml")
    class DummySvc:
        def __init__(self):
            self.send_message = mocker.AsyncMock()

    svc = DummySvc()
    runtime.dispatcher.register_service_handler("discord", svc)
    await runtime.dispatcher.dispatch(HandlerActionType.SPEAK, Thought(thought_id="t", source_task_id="task", created_at="", updated_at="", round_created=0, content=""), {"content": "x"}, {"discord_service": svc})
    svc.send_message.assert_awaited_once()

    svc.send_message.reset_mock()
    runtime.dreaming = True
    runtime.dispatcher.action_filter = runtime._dream_action_filter
    await runtime.dispatcher.dispatch(HandlerActionType.SPEAK, Thought(thought_id="t2", source_task_id="task", created_at="", updated_at="", round_created=0, content=""), {"content": "x"}, {"discord_service": svc})
    svc.send_message.assert_not_awaited()

@pytest.mark.asyncio
async def test_dream_protocol_emits_snore(mocker):
    adapter = DummyAdapter()
    runtime = BaseRuntime(adapter, "ciris_profiles/student.yaml", snore_channel_id="c")
    log_mock = mocker.AsyncMock()
    runtime.audit_service.log_action = log_mock
    await runtime.run_dream(duration=0.1, pulse_interval=0.05)

    assert any("snore" in o[1] for o in adapter.outputs)
    assert any("Dream ended" in o[1] for o in adapter.outputs)
    assert log_mock.await_count >= 2

