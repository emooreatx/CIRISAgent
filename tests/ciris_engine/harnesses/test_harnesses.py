import asyncio
import types
import pytest
from unittest.mock import AsyncMock

from ciris_engine.harnesses import (
    run_wakeup,
    run_play_session,
    run_solitude_session,
    schedule_reflection_modes,
    schedule_event_log_rotation,
    StopHarness,
    run_work_rounds,
    run_dream_session,
)
from ciris_engine.harnesses.work_mode import run_work_rounds
from ciris_engine.harnesses.dream_mode import run_dream_session
from ciris_engine.processor import WakeupProcessor, WorkProcessor, DreamProcessor
from ciris_engine.processor.thought_processor import ThoughtProcessor
from ciris_engine.schemas.config_schemas_v1 import AppConfig, WorkflowConfig
from ciris_engine.services.event_log_service import EventLogService
from ciris_engine.action_handlers.action_dispatcher import ActionDispatcher
from ciris_engine.processor.main_processor import AgentProcessor
from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus


# Reuse MemoryDB from processor tests for persistence mocks
class MemoryDB:
    def __init__(self):
        self.tasks = {}
        self.thoughts = {}

    def add_task(self, task: Task):
        self.tasks[task.task_id] = task

    def task_exists(self, task_id: str) -> bool:
        return task_id in self.tasks

    def get_task_by_id(self, task_id: str):
        return self.tasks.get(task_id)

    def update_task_status(self, task_id: str, status: TaskStatus, **kwargs):
        t = self.tasks.get(task_id)
        if not t:
            return False
        self.tasks[task_id] = t.copy(update={"status": status})
        return True

    def get_pending_tasks_for_activation(self, limit: int = 10):
        return [t for t in self.tasks.values() if t.status == TaskStatus.PENDING][:limit]

    def count_active_tasks(self):
        return len([t for t in self.tasks.values() if t.status == TaskStatus.ACTIVE])

    def get_tasks_needing_seed_thought(self, limit: int = 50):
        return [
            t
            for t in self.tasks.values()
            if t.status == TaskStatus.ACTIVE and not self.thought_exists_for(t.task_id)
        ][:limit]

    def add_thought(self, thought: Thought):
        self.thoughts[thought.thought_id] = thought

    def thought_exists_for(self, task_id: str) -> bool:
        return any(th.source_task_id == task_id for th in self.thoughts.values())

    def get_pending_thoughts_for_active_tasks(self, limit: int = 50):
        active_ids = {t.task_id for t in self.tasks.values() if t.status == TaskStatus.ACTIVE}
        pending = [
            th
            for th in self.thoughts.values()
            if th.status == ThoughtStatus.PENDING and th.source_task_id in active_ids
        ]
        return pending[:limit]

    def update_thought_status(self, thought_id: str, status: ThoughtStatus, **kwargs):
        th = self.thoughts.get(thought_id)
        if not th:
            return False
        self.thoughts[thought_id] = th.copy(update={"status": status})
        return True

    def pending_thoughts(self):
        return [th for th in self.thoughts.values() if th.status == ThoughtStatus.PENDING]

    def count_pending_thoughts_for_active_tasks(self):
        return len(self.get_pending_thoughts_for_active_tasks())


@pytest.mark.asyncio
async def test_run_wakeup(monkeypatch):
    db = MemoryDB()
    monkeypatch.setattr("ciris_engine.persistence.task_exists", db.task_exists)
    monkeypatch.setattr("ciris_engine.persistence.add_task", db.add_task)
    monkeypatch.setattr("ciris_engine.persistence.get_task_by_id", db.get_task_by_id)
    monkeypatch.setattr("ciris_engine.persistence.update_task_status", db.update_task_status)

    dispatcher = ActionDispatcher({})
    processor = AgentProcessor(AppConfig(), AsyncMock(spec=ThoughtProcessor), dispatcher, {})

    out = []
    await run_wakeup(processor, out.append, non_blocking=True)
    assert out
    assert processor.wakeup_processor.wakeup_tasks


@pytest.mark.asyncio
async def test_run_work_rounds(monkeypatch):
    cfg = AppConfig(workflow=WorkflowConfig(max_active_tasks=1, max_active_thoughts=1))
    db = MemoryDB()
    monkeypatch.setattr("ciris_engine.persistence.task_exists", db.task_exists)
    monkeypatch.setattr("ciris_engine.persistence.add_task", db.add_task)
    monkeypatch.setattr("ciris_engine.persistence.get_task_by_id", db.get_task_by_id)
    monkeypatch.setattr("ciris_engine.persistence.update_task_status", db.update_task_status)
    monkeypatch.setattr("ciris_engine.persistence.get_pending_tasks_for_activation", db.get_pending_tasks_for_activation, raising=False)
    monkeypatch.setattr("ciris_engine.persistence.count_active_tasks", db.count_active_tasks, raising=False)
    monkeypatch.setattr("ciris_engine.persistence.get_tasks_needing_seed_thought", db.get_tasks_needing_seed_thought, raising=False)
    monkeypatch.setattr("ciris_engine.persistence.add_thought", db.add_thought)
    monkeypatch.setattr("ciris_engine.persistence.thought_exists_for", db.thought_exists_for, raising=False)
    monkeypatch.setattr("ciris_engine.persistence.get_pending_thoughts_for_active_tasks", db.get_pending_thoughts_for_active_tasks)
    monkeypatch.setattr("ciris_engine.persistence.update_thought_status", db.update_thought_status)
    monkeypatch.setattr("ciris_engine.persistence.pending_thoughts", db.pending_thoughts, raising=False)
    monkeypatch.setattr("ciris_engine.persistence.count_pending_thoughts_for_active_tasks", db.count_pending_thoughts_for_active_tasks, raising=False)

    dispatcher = ActionDispatcher({})
    work = WorkProcessor(app_config=cfg, thought_processor=AsyncMock(), action_dispatcher=dispatcher, services={})
    db.add_task(Task(task_id="t1", description="d", status=TaskStatus.PENDING, priority=0, created_at="now", updated_at="now"))
    results = await run_work_rounds(work, rounds=2)
    assert len(results) == 2


@pytest.mark.asyncio
async def test_run_dream_session(monkeypatch):
    dp = DreamProcessor(cirisnode_url="http://x", pulse_interval=0.05)

    class DummyClient:
        async def run_he300(self):
            return {"topic": "A"}
        async def run_simplebench(self):
            return {"score": 1}

    dp.cirisnode_client = DummyClient()
    summary = await run_dream_session(dp, duration=0.15, pulse_interval=0.05)
    assert summary["metrics"]["total_pulses"] >= 1


@pytest.mark.asyncio
async def test_play_and_solitude_sessions():
    msgs = []
    async def out(msg):
        msgs.append(msg)
    await run_play_session(out, duration=0.01)
    await run_solitude_session(out, duration=0.01)
    assert any("Play Mode" in m or "Solitude" in m for m in msgs[-2:])


@pytest.mark.asyncio
async def test_schedule_reflection_modes():
    msgs = []
    async def out(msg):
        msgs.append(msg)
    async def dummy_play(_):
        msgs.append("play")
    async def dummy_solitude(_):
        msgs.append("solitude")
    mp = pytest.MonkeyPatch()
    mp.setattr("ciris_engine.harnesses.reflection_scheduler.run_play_session", dummy_play)
    mp.setattr("ciris_engine.harnesses.reflection_scheduler.run_solitude_session", dummy_solitude)
    await schedule_reflection_modes(out, interval=0.01, iterations=2)
    mp.undo()
    assert msgs.count("play") + msgs.count("solitude") == 2


@pytest.mark.asyncio
async def test_schedule_event_log_rotation(tmp_path):
    service = EventLogService(log_path=tmp_path / "log.jsonl", max_bytes=1, backups=1)
    await service.start()
    await service.log_event({"e": 1})
    task = asyncio.create_task(schedule_event_log_rotation(service, interval=0.01))
    await asyncio.sleep(0.02)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    rotated = tmp_path / "log.1.jsonl"
    assert rotated.exists()


@pytest.mark.asyncio
async def test_stop_harness(monkeypatch):
    class DummyProc:
        def __init__(self):
            self.stopped = False
            self.persisted = False
        async def stop_processing(self):
            self.stopped = True
        async def persist_state(self):
            self.persisted = True
        async def self_test(self):
            return True

    proc = DummyProc()
    harness = StopHarness(proc)
    with harness:
        harness._handle_signal(2, None)
        await asyncio.wait_for(harness.wait_for_stop(0.01), timeout=0.5)
    assert proc.stopped and proc.persisted
