import asyncio
import types
import pytest
from unittest.mock import AsyncMock

from ciris_engine.runtime.base_runtime import BaseRuntime, BaseIOAdapter
from ciris_engine.action_handlers.action_dispatcher import ActionDispatcher
from ciris_engine.schemas.agent_core_schemas_v1 import Task
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType


class DummyAdapter(BaseIOAdapter):
    def __init__(self):
        self.outputs = []
    async def send_output(self, target, content):
        self.outputs.append((target, content))


class MemoryDB:
    def __init__(self):
        self.tasks = {}
    def add_task(self, t: Task):
        self.tasks[t.task_id] = t
    def task_exists(self, tid: str) -> bool:
        return tid in self.tasks
    def get_task_by_id(self, tid: str):
        return self.tasks.get(tid)


@pytest.mark.asyncio
async def test_create_task_if_new(monkeypatch):
    db = MemoryDB()
    monkeypatch.setattr("ciris_engine.persistence.task_exists", db.task_exists)
    monkeypatch.setattr("ciris_engine.persistence.add_task", db.add_task)
    rt = BaseRuntime(DummyAdapter(), "profile", ActionDispatcher({}))
    created = await rt._create_task_if_new("1", "hello", {})
    assert created
    assert db.task_exists("1")
    created2 = await rt._create_task_if_new("1", "hello", {})
    assert not created2


@pytest.mark.asyncio
async def test_dream_action_filter(monkeypatch):
    rt = BaseRuntime(DummyAdapter(), "profile", ActionDispatcher({}))
    rt.audit_service = AsyncMock()

    result = types.SimpleNamespace(selected_handler_action=HandlerActionType.SPEAK)
    skip = await rt._dream_action_filter(result, {"a": 1})
    assert skip
    rt.audit_service.log_action.assert_awaited()

    result2 = types.SimpleNamespace(selected_handler_action=HandlerActionType.PONDER)
    rt.audit_service.log_action.reset_mock()
    skip = await rt._dream_action_filter(result2, {})
    assert not skip
    rt.audit_service.log_action.assert_not_called()


@pytest.mark.asyncio
async def test_run_dream(monkeypatch):
    adapter = DummyAdapter()
    rt = BaseRuntime(adapter, "profile", ActionDispatcher({}), snore_channel_id="chan")
    rt.audit_service = AsyncMock()
    monkeypatch.setattr(rt, "_dream_action_filter", AsyncMock(return_value=False))
    await rt.run_dream(duration=0.15, pulse_interval=0.05)
    assert not rt.dreaming
    assert adapter.outputs
    rt.audit_service.log_action.assert_called()
