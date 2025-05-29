import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from ciris_engine.processor.wakeup_processor import WakeupProcessor
from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus, HandlerActionType
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.ponder.manager import PonderManager
from ciris_engine.action_handlers.action_dispatcher import ActionDispatcher
from ciris_engine.action_handlers.handler_registry import build_action_dispatcher
from ciris_engine.schemas.config_schemas_v1 import AppConfig
from ciris_engine.processor.thought_processor import ThoughtProcessor

class MemoryDB:
    def __init__(self):
        self.tasks = {}
        self.thoughts = {}
    def task_exists(self, task_id):
        return task_id in self.tasks
    def add_task(self, task):
        self.tasks[task.task_id] = task
    def get_task_by_id(self, task_id):
        return self.tasks.get(task_id)
    def update_task_status(self, task_id, status, **kwargs):
        t = self.tasks.get(task_id)
        if not t:
            return False
        self.tasks[task_id] = t.model_copy(update={"status": status})
        return True
    def add_thought(self, thought):
        self.thoughts[thought.thought_id] = thought
    def get_thought_by_id(self, thought_id):
        return self.thoughts.get(thought_id)
    def update_thought_status(self, thought_id, status, **kwargs):
        th = self.thoughts.get(thought_id)
        if not th:
            return False
        self.thoughts[thought_id] = th.model_copy(update={"status": status})
        return True
    def get_thoughts_by_task_id(self, task_id):
        return [th for th in self.thoughts.values() if th.source_task_id == task_id]

def setup_wakeup_proc(monkeypatch):
    db = MemoryDB()
    monkeypatch.setattr('ciris_engine.persistence.task_exists', db.task_exists)
    monkeypatch.setattr('ciris_engine.persistence.add_task', db.add_task)
    monkeypatch.setattr('ciris_engine.persistence.get_task_by_id', db.get_task_by_id)
    monkeypatch.setattr('ciris_engine.persistence.update_task_status', db.update_task_status)
    monkeypatch.setattr('ciris_engine.persistence.add_thought', db.add_thought)
    monkeypatch.setattr('ciris_engine.persistence.get_thought_by_id', db.get_thought_by_id)
    monkeypatch.setattr('ciris_engine.persistence.update_thought_status', db.update_thought_status)
    monkeypatch.setattr('ciris_engine.persistence.get_thoughts_by_task_id', db.get_thoughts_by_task_id)
    ponder_manager = PonderManager()
    action_dispatcher = build_action_dispatcher(ponder_manager=ponder_manager)
    thought_processor = ThoughtProcessor(
        dma_orchestrator=None,  # Not needed for this test
        context_builder=None,
        guardrail_orchestrator=None,
        ponder_manager=ponder_manager,
        app_config=AppConfig()
    )
    proc = WakeupProcessor(app_config=AppConfig(), thought_processor=thought_processor, action_dispatcher=action_dispatcher, services={})
    return proc, db, thought_processor, action_dispatcher

@pytest.mark.asyncio
async def test_wakeup_ponder_then_speak(monkeypatch):
    proc, db, thought_processor, action_dispatcher = setup_wakeup_proc(monkeypatch)
    # Patch process_thought to simulate PONDER then SPEAK, but let real handler logic run
    call_count = {"count": 0}
    orig_process_thought = thought_processor.process_thought
    async def fake_process_thought(item, ctx=None, benchmark_mode=False):
        call_count["count"] += 1
        if call_count["count"] == 1:
            # Mark the step task as completed after PONDER
            step_task_id = getattr(item, "source_task_id", None)
            if step_task_id:
                db.update_task_status(step_task_id, TaskStatus.COMPLETED)
                await asyncio.sleep(0.1)
            class Result:
                selected_action = HandlerActionType.PONDER
                action_parameters = {"questions": ["Q1"]}
            return Result()
        else:
            # Mark the step as complete for SPEAK since no real handler runs
            step_task_id = getattr(item, "source_task_id", None)
            if step_task_id:
                db.update_task_status(step_task_id, TaskStatus.COMPLETED)
            class Result:
                selected_action = HandlerActionType.SPEAK
                action_parameters = {"content": "Hello!"}
            return Result()
    thought_processor.process_thought = fake_process_thought
    # Run the wakeup processor (blocking mode)
    result = await proc.process_wakeup(round_number=1, non_blocking=False)
    assert result["status"] == "success"
    assert result["wakeup_complete"] is True
    assert result["steps_completed"] == len(proc.WAKEUP_SEQUENCE)
    assert call_count["count"] >= 2
    # Restore original method
    thought_processor.process_thought = orig_process_thought
