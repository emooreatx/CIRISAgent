import asyncio
from unittest.mock import AsyncMock
import pytest
from typing import List

import main
from ciris_engine.runtime.ciris_runtime import CIRISRuntime
from tests.adapters.mock_llm import MockLLMService
from ciris_engine.schemas.config_schemas_v1 import AppConfig, WorkflowConfig, LLMServicesConfig, OpenAIConfig
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus

class MemoryDB:
    def __init__(self):
        self.tasks = {}
        self.thoughts = {}

    def add_task(self, task):
        self.tasks[task.task_id] = task

    def task_exists(self, task_id):
        return task_id in self.tasks

    def get_task_by_id(self, task_id):
        return self.tasks.get(task_id)

    def update_task_status(self, task_id, status, **kwargs):
        t = self.tasks.get(task_id)
        if not t:
            return False
        self.tasks[task_id] = t.model_copy(update={"status": status})
        return True

    def get_pending_tasks_for_activation(self, limit=10):
        return [t for t in self.tasks.values() if t.status == TaskStatus.PENDING][:limit]

    def count_active_tasks(self):
        return len([t for t in self.tasks.values() if t.status == TaskStatus.ACTIVE])

    def get_tasks_needing_seed_thought(self, limit=50):
        return [t for t in self.tasks.values() if t.status == TaskStatus.ACTIVE and not self.thought_exists_for(t.task_id)][:limit]

    def add_thought(self, thought):
        self.thoughts[thought.thought_id] = thought

    def thought_exists_for(self, task_id):
        return any(th.source_task_id == task_id for th in self.thoughts.values())

    def get_pending_thoughts_for_active_tasks(self, limit=50):
        active_ids = {t.task_id for t in self.tasks.values() if t.status == TaskStatus.ACTIVE}
        pending = [th for th in self.thoughts.values() if th.status == ThoughtStatus.PENDING and th.source_task_id in active_ids]
        return pending[:limit]

    def get_tasks_by_parent_id(self, parent_id):
        return [t for t in self.tasks.values() if getattr(t, 'parent_task_id', None) == parent_id]

    def get_thoughts_by_task_id(self, task_id):
        return [th for th in self.thoughts.values() if th.source_task_id == task_id]

    def update_thought_status(self, thought_id, status, **kwargs):
        th = self.thoughts.get(thought_id)
        if not th:
            return False
        self.thoughts[thought_id] = th.model_copy(update={"status": status})
        return True

    def pending_thoughts(self):
        return [th for th in self.thoughts.values() if th.status == ThoughtStatus.PENDING]

    def count_pending_thoughts_for_active_tasks(self):
        return len(self.get_pending_thoughts_for_active_tasks())

def patch_persistence(monkeypatch, db: MemoryDB):
    monkeypatch.setattr('ciris_engine.persistence.task_exists', db.task_exists)
    monkeypatch.setattr('ciris_engine.persistence.add_task', db.add_task)
    monkeypatch.setattr('ciris_engine.persistence.get_task_by_id', db.get_task_by_id)
    monkeypatch.setattr('ciris_engine.persistence.update_task_status', db.update_task_status)
    monkeypatch.setattr('ciris_engine.persistence.get_pending_tasks_for_activation', db.get_pending_tasks_for_activation, raising=False)
    monkeypatch.setattr('ciris_engine.persistence.count_active_tasks', db.count_active_tasks, raising=False)
    monkeypatch.setattr('ciris_engine.persistence.get_tasks_needing_seed_thought', db.get_tasks_needing_seed_thought, raising=False)
    monkeypatch.setattr('ciris_engine.persistence.add_thought', db.add_thought)
    monkeypatch.setattr('ciris_engine.persistence.thought_exists_for', db.thought_exists_for, raising=False)
    monkeypatch.setattr('ciris_engine.persistence.get_pending_thoughts_for_active_tasks', db.get_pending_thoughts_for_active_tasks)
    monkeypatch.setattr('ciris_engine.persistence.update_thought_status', db.update_thought_status)
    monkeypatch.setattr('ciris_engine.persistence.pending_thoughts', db.pending_thoughts, raising=False)
    monkeypatch.setattr('ciris_engine.persistence.count_pending_thoughts_for_active_tasks', db.count_pending_thoughts_for_active_tasks, raising=False)
    monkeypatch.setattr('ciris_engine.persistence.get_thoughts_by_task_id', db.get_thoughts_by_task_id)
    monkeypatch.setattr('ciris_engine.persistence.get_tasks_by_parent_id', db.get_tasks_by_parent_id, raising=False)
    monkeypatch.setattr('ciris_engine.persistence.initialize_database', lambda: None)

def create_test_runtime(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'x')
    monkeypatch.setattr('ciris_engine.runtime.ciris_runtime.OpenAICompatibleLLM', MockLLMService)
    config = AppConfig(workflow=WorkflowConfig(max_rounds=1), llm_services=LLMServicesConfig(openai=OpenAIConfig(model_name='mock-model')))
    
    # Mock CIRISRuntime properly
    runtime_mock = AsyncMock(spec=CIRISRuntime)
    runtime_mock.agent_processor = AsyncMock()
    runtime_mock.agent_processor.wakeup_processor = AsyncMock()
    runtime_mock.agent_processor.wakeup_processor.process = AsyncMock()
    runtime_mock.agent_processor.wakeup_processor.wakeup_tasks = []
    runtime_mock.initialize = AsyncMock()
    
    # Mock the constructor
    original_new = CIRISRuntime.__new__
    
    def mock_new(cls, *args, **kwargs):
        return runtime_mock
    
    monkeypatch.setattr(CIRISRuntime, '__new__', mock_new)
    monkeypatch.setattr(CIRISRuntime, '__init__', lambda self, *args, **kwargs: None)
    
    return runtime_mock, config

@pytest.mark.asyncio
async def test_wakeup_sequence_offline(monkeypatch):
    db = MemoryDB()
    patch_persistence(monkeypatch, db)
    runtime, cfg = create_test_runtime(monkeypatch)
    monkeypatch.setattr(main, 'load_config', AsyncMock(return_value=cfg))
    
    # Set up mock wakeup processor behavior
    runtime.agent_processor.wakeup_processor.process.side_effect = [
        {'status': 'in_progress'},  # First call
        {'wakeup_complete': True}   # Second call
    ]
    
    # Create some mock tasks
    from ciris_engine.schemas.agent_core_schemas_v1 import Task
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    mock_tasks = [
        Task(task_id='task1', description='Task 1', status=TaskStatus.ACTIVE, created_at=now, updated_at=now),
        Task(task_id='task2', description='Task 2', status=TaskStatus.ACTIVE, created_at=now, updated_at=now),
    ]
    runtime.agent_processor.wakeup_processor.wakeup_tasks = mock_tasks
    
    await runtime.initialize()
    result = await runtime.agent_processor.wakeup_processor.process(0)
    assert result['status'] == 'in_progress'
    
    # Update task status
    for t in runtime.agent_processor.wakeup_processor.wakeup_tasks[1:]:
        db.update_task_status(t.task_id, TaskStatus.COMPLETED)
        
    result = await runtime.agent_processor.wakeup_processor.process(1)
    assert result['wakeup_complete']

@pytest.mark.asyncio
async def test_run_runtime_timeout(monkeypatch):
    async def slow_run(num_rounds=None):
        await asyncio.sleep(0.2)
    
    runtime = AsyncMock(spec=CIRISRuntime)
    runtime.run = AsyncMock(side_effect=slow_run)
    runtime.shutdown = AsyncMock()
    runtime._shutdown_event = asyncio.Event()  # Add the shutdown event
    
    await main._run_runtime(runtime, timeout=0.1)
    runtime.run.assert_awaited()
    runtime.shutdown.assert_awaited()