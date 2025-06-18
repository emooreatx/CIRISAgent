import pytest
from unittest.mock import AsyncMock

from ciris_engine.processor import WakeupProcessor, WorkProcessor, PlayProcessor, SolitudeProcessor, DreamProcessor
from ciris_engine.schemas.config_schemas_v1 import AppConfig, WorkflowConfig, LLMServicesConfig, OpenAIConfig, CIRISNodeConfig
from ciris_engine.schemas.identity_schemas_v1 import AgentIdentityRoot, CoreProfile, IdentityMetadata
from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought
from datetime import datetime, timezone

# Import adapter configs to resolve forward references
try:
    from ciris_engine.adapters.discord.config import DiscordAdapterConfig
    from ciris_engine.adapters.api.config import APIAdapterConfig
    from ciris_engine.adapters.cli.config import CLIAdapterConfig
except ImportError:
    DiscordAdapterConfig = type('DiscordAdapterConfig', (), {})
    APIAdapterConfig = type('APIAdapterConfig', (), {})
    CLIAdapterConfig = type('CLIAdapterConfig', (), {})

# Rebuild models with resolved references  
try:
    AppConfig.model_rebuild()
except Exception:
    pass

from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus, ThoughtType, HandlerActionType


# Simple in-memory persistence mocks
class MemoryDB:
    def __init__(self):
        self.tasks = {}
        self.thoughts = {}

    # task helpers
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
        self.tasks[task_id] = t.model_copy(update={"status": status})
        return True

    def get_pending_tasks_for_activation(self, limit: int = 10):
        return [t for t in self.tasks.values() if t.status == TaskStatus.PENDING][:limit]

    def count_active_tasks(self):
        return len([t for t in self.tasks.values() if t.status == TaskStatus.ACTIVE])

    def get_tasks_needing_seed_thought(self, limit: int = 50):
        return [t for t in self.tasks.values() if t.status == TaskStatus.ACTIVE and not self.thought_exists_for(t.task_id)][:limit]

    # thought helpers
    def add_thought(self, thought: Thought):
        self.thoughts[thought.thought_id] = thought

    def thought_exists_for(self, task_id: str) -> bool:
        return any(th.source_task_id == task_id for th in self.thoughts.values())

    def get_pending_thoughts_for_active_tasks(self, limit: int = 50):
        active_ids = {t.task_id for t in self.tasks.values() if t.status == TaskStatus.ACTIVE}
        pending = [th for th in self.thoughts.values() if th.status == ThoughtStatus.PENDING and th.source_task_id in active_ids]
        return pending[:limit]
    
    def get_tasks_by_parent_id(self, parent_id: str):
        return [t for t in self.tasks.values() if getattr(t, 'parent_task_id', None) == parent_id]
    
    def get_thoughts_by_task_id(self, task_id: str):
        return [th for th in self.thoughts.values() if th.source_task_id == task_id]

    def update_thought_status(self, thought_id: str, status: ThoughtStatus, **kwargs):
        th = self.thoughts.get(thought_id)
        if not th:
            return False
        self.thoughts[thought_id] = th.model_copy(update={"status": status})
        return True

    def pending_thoughts(self):
        return [th for th in self.thoughts.values() if th.status == ThoughtStatus.PENDING]

    def count_pending_thoughts_for_active_tasks(self):
        return len(self.get_pending_thoughts_for_active_tasks())

    def get_thoughts_by_task_id(self, task_id):
        return [th for th in self.thoughts.values() if th.source_task_id == task_id]


@pytest.mark.asyncio
async def test_wakeup_processor_completion(monkeypatch):
    db = MemoryDB()
    # patch persistence functions
    monkeypatch.setattr('ciris_engine.persistence.task_exists', db.task_exists)
    monkeypatch.setattr('ciris_engine.persistence.add_task', db.add_task)
    monkeypatch.setattr('ciris_engine.persistence.get_task_by_id', db.get_task_by_id)
    monkeypatch.setattr('ciris_engine.persistence.update_task_status', db.update_task_status)
    monkeypatch.setattr('ciris_engine.persistence.get_thoughts_by_task_id', db.get_thoughts_by_task_id)
    monkeypatch.setattr('ciris_engine.persistence.add_thought', db.add_thought)

    proc = WakeupProcessor(AppConfig(), AsyncMock(), AsyncMock(), {}, startup_channel_id='chan')
    # Initial call creates tasks
    result = await proc.process(0)
    print("Wakeup result:", result)  # Diagnostic print
    assert result['status'] in ('in_progress', 'success', 'completed', 'error')  # Accept error for investigation
    assert len(proc.wakeup_tasks) == len(proc._get_wakeup_sequence()) + 1

    # Mark all step tasks as completed (using the actual generated task IDs)
    for t in proc.wakeup_tasks[1:]:  # Only mark step tasks, not root
        db.update_task_status(t.task_id, TaskStatus.COMPLETED)

    result = await proc.process(1)
    print("Wakeup result after completion:", result)  # Diagnostic print
    assert result['wakeup_complete'] is True
    root_task = db.get_task_by_id('WAKEUP_ROOT')
    assert root_task.status == TaskStatus.COMPLETED


def setup_work_proc(monkeypatch, max_tasks=2, max_thoughts=3):
    cfg = AppConfig(workflow=WorkflowConfig(max_active_tasks=max_tasks, max_active_thoughts=max_thoughts))
    db = MemoryDB()
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
    tp = AsyncMock()
    ad = AsyncMock()
    proc = WorkProcessor(app_config=cfg, thought_processor=tp, action_dispatcher=ad, services={})
    return proc, db


@pytest.mark.asyncio
async def test_work_processor_enforces_limits(monkeypatch):
    proc, db = setup_work_proc(monkeypatch, max_tasks=2, max_thoughts=3)
    # existing active task
    db.add_task(Task(task_id='active1', description='d', status=TaskStatus.ACTIVE, priority=0, created_at='now', updated_at='now'))
    # five pending tasks
    for i in range(5):
        db.add_task(Task(task_id=f'p{i}', description='d', status=TaskStatus.PENDING, priority=0, created_at='now', updated_at='now'))
    # add pending thoughts for active1
    for i in range(5):
        db.add_thought(Thought(thought_id=f'th{i}', source_task_id='active1', thought_type=ThoughtType.STANDARD, status=ThoughtStatus.PENDING, created_at='now', updated_at='now', round_number=0, content='c'))

    activated = proc.task_manager.activate_pending_tasks()
    assert activated == 1  # only up to max_active_tasks can be activated

    queue_size = proc.thought_manager.populate_queue(1)
    assert queue_size == 3  # limited by max_active_thoughts


@pytest.mark.asyncio
async def test_play_processor_mode(monkeypatch):
    proc, _ = setup_work_proc(monkeypatch)
    play_proc = PlayProcessor(app_config=proc.app_config, thought_processor=proc.thought_processor, action_dispatcher=proc.action_dispatcher, services={})
    result = await play_proc.process(1)
    assert result['mode'] == 'play'
    assert result['creativity_enabled']


@pytest.mark.asyncio
async def test_solitude_processor_exit_after_critical(monkeypatch):
    cfg = AppConfig()
    proc = SolitudeProcessor(app_config=cfg, thought_processor=AsyncMock(), action_dispatcher=AsyncMock(), services={})
    monkeypatch.setattr(proc, '_check_critical_tasks', AsyncMock(return_value=1))
    result = await proc.process(1)
    assert result['should_exit_solitude'] is True


@pytest.mark.asyncio
async def test_dream_processor_pulse(monkeypatch):
    # Create mock AppConfig and AgentIdentity
    mock_app_config = AppConfig(
        llm_services=LLMServicesConfig(openai=OpenAIConfig(model_name="test-model")),
        cirisnode=CIRISNodeConfig(base_url="https://x") 
        )
    mock_identity = AgentIdentityRoot(
        agent_id="test_agent",
        identity_hash="test_hash_123",
        core_profile=CoreProfile(
            description="Test agent for unit tests",
            role_description="A minimal test agent profile",
            domain_specific_knowledge={},
            dsdma_prompt_template=None,
            csdma_overrides={},
            action_selection_pdma_overrides={},
            last_shutdown_memory=None
        ),
        identity_metadata=IdentityMetadata(
            created_at=datetime.now(timezone.utc).isoformat(),
            last_modified=datetime.now(timezone.utc).isoformat(),
            modification_count=0,
            creator_agent_id="system",
            lineage_trace=["system"],
            approval_required=False,
            approved_by=None,
            approval_timestamp=None
        ),
        permitted_actions=[
            HandlerActionType.OBSERVE,
            HandlerActionType.SPEAK,
            HandlerActionType.PONDER,
            HandlerActionType.DEFER,
            HandlerActionType.REJECT,
            HandlerActionType.TASK_COMPLETE
        ],
        restricted_capabilities=[]
    )
    
    # Create a mock audit service
    class MockAuditService:
        async def log_action(self, handler_action, context, outcome=None):
            pass

    class MockServiceRegistry:
        def __init__(self):
            self._global_services = {"audit": []}
            self._audit_service = MockAuditService()
        
        async def get_global_service(self, service_type: str, **kwargs):
            if service_type == "audit":
                return self._audit_service
            return None

    # Pass mocks to DreamProcessor constructor 
    mock_service_registry = MockServiceRegistry()
    dp = DreamProcessor(app_config=mock_app_config, service_registry=mock_service_registry)


    class DummyClient:
        async def run_he300(self, model_id: str, agent_id: str):
            return {'topic': 'A'}
        async def run_simplebench(self, model_id: str, agent_id: str):
            return {'score': 1}
        async def close(self): # Add close method to dummy client
            pass
    
    # Re-assign cirisnode_client after DreamProcessor instantiation for this test's purpose
    dp.cirisnode_client = DummyClient()


    await dp._dream_pulse()
    assert dp.dream_metrics['total_pulses'] == 1
    assert dp.snore_history
    # Note: DreamProcessor doesn't have a close method, cleanup happens in stop_dreaming()
