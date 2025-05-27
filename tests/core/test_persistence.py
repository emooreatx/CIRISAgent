import pytest
import sqlite3
from pathlib import Path
import json
from datetime import datetime
import uuid

# Module to test
from ciris_engine.core import persistence
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus
from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought

# --- Fixtures ---

@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Provides a temporary database path for tests."""
    return tmp_path / "test_ciris_engine.db"

@pytest.fixture
def mock_db_path(monkeypatch, db_path: Path):
    """Mocks get_sqlite_db_full_path to use the temporary db_path."""
    monkeypatch.setattr(persistence, "get_sqlite_db_full_path", lambda: str(db_path))

@pytest.fixture
def initialized_db(mock_db_path):
    """Ensures the database is initialized for a test."""
    persistence.initialize_database()
    # Yield to run the test
    yield
    # Teardown: Clean up the db file if created by db_path fixture (tmp_path handles auto-cleanup)
    # if db_path.exists():
    #     db_path.unlink()


# --- Test Cases ---

def test_initialize_database(initialized_db, db_path: Path):
    """Test that database tables are created."""
    assert db_path.exists()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if tasks table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks';")
    assert cursor.fetchone() is not None, "tasks table not created"
    
    # Check if thoughts table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='thoughts';")
    assert cursor.fetchone() is not None, "thoughts table not created"
    
    conn.close()

def test_add_and_get_task(initialized_db):
    """Test adding a task and retrieving it."""
    now_iso = datetime.utcnow().isoformat()
    task_id = str(uuid.uuid4())
    task_data = Task(
        task_id=task_id,
        description="Test task for persistence",
        created_at=now_iso,
        updated_at=now_iso,
        priority=5,
        context={"info": "some context"},
        dependencies=["ual:task:another"]
    )
    
    returned_id = persistence.add_task(task_data)
    assert returned_id == task_id
    
    retrieved_task = persistence.get_task_by_id(task_id)
    assert retrieved_task is not None
    assert retrieved_task.task_id == task_id
    assert retrieved_task.description == "Test task for persistence"
    assert retrieved_task.priority == 5
    assert retrieved_task.status == TaskStatus.PENDING # Default
    assert retrieved_task.context == {"info": "some context"}
    assert retrieved_task.dependencies == ["ual:task:another"]

def test_add_and_get_thought(initialized_db):
    """Test adding a thought and retrieving it."""
    now_iso = datetime.utcnow().isoformat()
    task_id = str(uuid.uuid4())
    # Add a dummy task first for foreign key constraint
    dummy_task = Task(task_id=task_id, description="Dummy task", created_at=now_iso, updated_at=now_iso)
    persistence.add_task(dummy_task)

    thought_id = str(uuid.uuid4())
    thought_data = Thought(
        thought_id=thought_id,
        source_task_id=task_id,
        thought_type="test_type",
        content="Test thought content",
        created_at=now_iso,
        updated_at=now_iso,
        round_created=1,
        priority=3,
        processing_context={"detail": "proc context"}
    )
    
    returned_id = persistence.add_thought(thought_data)
    assert returned_id == thought_id
    
    retrieved_thought = persistence.get_thought_by_id(thought_id)
    assert retrieved_thought is not None
    assert retrieved_thought.thought_id == thought_id
    assert retrieved_thought.content == "Test thought content"
    assert retrieved_thought.priority == 3
    assert retrieved_thought.status == ThoughtStatus.PENDING
    assert retrieved_thought.round_created == 1
    assert retrieved_thought.processing_context == {"detail": "proc context"}

def test_update_task_status(initialized_db):
    now_iso = datetime.utcnow().isoformat()
    task_id = str(uuid.uuid4())
    task_data = Task(task_id=task_id, description="Task to update", created_at=now_iso, updated_at=now_iso)
    persistence.add_task(task_data)
    
    success = persistence.update_task_status(task_id, TaskStatus.ACTIVE)
    assert success
    
    updated_task = persistence.get_task_by_id(task_id)
    assert updated_task is not None
    assert updated_task.status == TaskStatus.ACTIVE

def test_update_thought_status(initialized_db):
    now_iso = datetime.utcnow().isoformat()
    task_id = str(uuid.uuid4())
    dummy_task = Task(task_id=task_id, description="Dummy task for thought", created_at=now_iso, updated_at=now_iso)
    persistence.add_task(dummy_task)

    thought_id = str(uuid.uuid4())
    thought_data = Thought(
        thought_id=thought_id, source_task_id=task_id, thought_type="test", content="Thought to update",
        created_at=now_iso, updated_at=now_iso, round_created=1
    )
    persistence.add_thought(thought_data)

    # Create a more complete ActionSelectionPDMAResult-like dict
    complete_action_result_dict = {
        "schema_version": "1.0-beta",
        "context_summary_for_action_selection": "Summary for persistence test",
        "action_alignment_check": {"speak": "aligned"},
        "selected_handler_action": "speak", 
        "action_parameters": {"content": "processed content for persistence"}, # This should match SpeakParams structure
        "action_selection_rationale": "Rationale for persistence test",
        "monitoring_for_selected_action": "Monitor persistence test",
        "confidence_score": 0.95,
        # Optional fields
        "action_conflicts": None,
        "action_resolution": None,
        "raw_llm_response": "raw response for persistence",
        "ethical_assessment_summary": {"status": "pass"},
        "csdma_assessment_summary": {"score": 0.9},
        "dsdma_assessment_summary": {"score": 0.8}
    }

    success = persistence.update_thought_status(
        thought_id, ThoughtStatus.PROCESSING, round_processed=1,
        final_action_result=complete_action_result_dict, ponder_count=1
    )
    assert success
    
    updated_thought = persistence.get_thought_by_id(thought_id)
    assert updated_thought is not None
    assert updated_thought.status == ThoughtStatus.PROCESSING
    assert updated_thought.round_processed == 1
    # Pydantic will have converted the dict to the ActionSelectionPDMAResult model
    assert updated_thought.final_action_result is not None
    assert updated_thought.final_action_result.selected_handler_action.value == "speak"
    # action_parameters is now a SpeakParams model instance
    from ciris_engine.schemas.agent_core_schemas_v1 import SpeakParams
    assert isinstance(updated_thought.final_action_result.action_parameters, SpeakParams)
    assert updated_thought.final_action_result.action_parameters.content == "processed content for persistence" # Corrected expected content
    assert updated_thought.ponder_count == 1

def test_count_active_tasks(initialized_db):
    now_iso = datetime.utcnow().isoformat()
    persistence.add_task(Task(task_id=str(uuid.uuid4()), description="t1", created_at=now_iso, updated_at=now_iso, status=TaskStatus.ACTIVE))
    persistence.add_task(Task(task_id=str(uuid.uuid4()), description="t2", created_at=now_iso, updated_at=now_iso, status=TaskStatus.PENDING))
    persistence.add_task(Task(task_id=str(uuid.uuid4()), description="t3", created_at=now_iso, updated_at=now_iso, status=TaskStatus.ACTIVE))
    
    assert persistence.count_active_tasks() == 2

def test_count_pending_thoughts(initialized_db):
    now_iso = datetime.utcnow().isoformat()
    task_id = str(uuid.uuid4())
    persistence.add_task(Task(task_id=task_id, description="Task for thoughts", created_at=now_iso, updated_at=now_iso))
    
    persistence.add_thought(Thought(thought_id=str(uuid.uuid4()), source_task_id=task_id, content="th1", thought_type="t", created_at=now_iso, updated_at=now_iso, round_created=1, status=ThoughtStatus.PENDING))
    persistence.add_thought(Thought(thought_id=str(uuid.uuid4()), source_task_id=task_id, content="th2", thought_type="t", created_at=now_iso, updated_at=now_iso, round_created=1, status=ThoughtStatus.PROCESSING))
    persistence.add_thought(Thought(thought_id=str(uuid.uuid4()), source_task_id=task_id, content="th3", thought_type="t", created_at=now_iso, updated_at=now_iso, round_created=1, status=ThoughtStatus.PENDING))

    assert persistence.count_pending_thoughts() == 2

def test_get_tasks_needing_seed_thought(initialized_db):
    now_iso = datetime.utcnow().isoformat()
    task1_id = str(uuid.uuid4()) # Active, no thoughts
    persistence.add_task(Task(task_id=task1_id, description="Task 1", created_at=now_iso, updated_at=now_iso, status=TaskStatus.ACTIVE, priority=10))
    
    task2_id = str(uuid.uuid4()) # Active, but has a pending thought
    persistence.add_task(Task(task_id=task2_id, description="Task 2", created_at=now_iso, updated_at=now_iso, status=TaskStatus.ACTIVE, priority=5))
    persistence.add_thought(Thought(thought_id=str(uuid.uuid4()), source_task_id=task2_id, content="th_for_t2", thought_type="t", created_at=now_iso, updated_at=now_iso, round_created=1, status=ThoughtStatus.PENDING))

    task3_id = str(uuid.uuid4()) # Pending, should not be seeded
    persistence.add_task(Task(task_id=task3_id, description="Task 3", created_at=now_iso, updated_at=now_iso, status=TaskStatus.PENDING, priority=20))

    task4_id = str(uuid.uuid4()) # Active, all thoughts completed
    persistence.add_task(Task(task_id=task4_id, description="Task 4", created_at=now_iso, updated_at=now_iso, status=TaskStatus.ACTIVE, priority=1))
    persistence.add_thought(Thought(thought_id=str(uuid.uuid4()), source_task_id=task4_id, content="th_for_t4", thought_type="t", created_at=now_iso, updated_at=now_iso, round_created=1, status=ThoughtStatus.COMPLETED))

    tasks_needing_seed = persistence.get_tasks_needing_seed_thought(limit=5)
    
    task_ids_needing_seed = {t.task_id for t in tasks_needing_seed}
    assert task1_id in task_ids_needing_seed
    assert task4_id in task_ids_needing_seed # Task 4 needs seed because its only thought is completed
    assert task2_id not in task_ids_needing_seed
    assert task3_id not in task_ids_needing_seed
    assert len(tasks_needing_seed) == 2
    # Check order (task1 has higher priority)
    if len(tasks_needing_seed) == 2:
         assert tasks_needing_seed[0].task_id == task1_id # Higher priority
         assert tasks_needing_seed[1].task_id == task4_id


def test_get_pending_thoughts_for_active_tasks(initialized_db):
    now_iso = datetime.utcnow().isoformat()
    # Task 1 (Active)
    task1_id = str(uuid.uuid4())
    persistence.add_task(Task(task_id=task1_id, description="Active Task 1", created_at=now_iso, updated_at=now_iso, status=TaskStatus.ACTIVE, priority=10))
    thought1_t1_id = str(uuid.uuid4()) # Pending
    persistence.add_thought(Thought(thought_id=thought1_t1_id, source_task_id=task1_id, content="t1_th1_pending", thought_type="t", created_at=now_iso, updated_at=now_iso, round_created=1, status=ThoughtStatus.PENDING, priority=1))
    thought2_t1_id = str(uuid.uuid4()) # Processing
    persistence.add_thought(Thought(thought_id=thought2_t1_id, source_task_id=task1_id, content="t1_th2_processing", thought_type="t", created_at=now_iso, updated_at=now_iso, round_created=1, status=ThoughtStatus.PROCESSING, priority=2))

    # Task 2 (Active)
    task2_id = str(uuid.uuid4())
    persistence.add_task(Task(task_id=task2_id, description="Active Task 2", created_at=now_iso, updated_at=now_iso, status=TaskStatus.ACTIVE, priority=5))
    thought1_t2_id = str(uuid.uuid4()) # Pending
    persistence.add_thought(Thought(thought_id=thought1_t2_id, source_task_id=task2_id, content="t2_th1_pending", thought_type="t", created_at=now_iso, updated_at=now_iso, round_created=1, status=ThoughtStatus.PENDING, priority=5))

    # Task 3 (Pending)
    task3_id = str(uuid.uuid4())
    persistence.add_task(Task(task_id=task3_id, description="Pending Task 3", created_at=now_iso, updated_at=now_iso, status=TaskStatus.PENDING, priority=100))
    thought1_t3_id = str(uuid.uuid4()) # Pending
    persistence.add_thought(Thought(thought_id=thought1_t3_id, source_task_id=task3_id, content="t3_th1_pending", thought_type="t", created_at=now_iso, updated_at=now_iso, round_created=1, status=ThoughtStatus.PENDING, priority=10))

    pending_thoughts = persistence.get_pending_thoughts_for_active_tasks(limit=5)
    
    assert len(pending_thoughts) == 2
    pending_thought_ids = {th.thought_id for th in pending_thoughts}
    assert thought1_t1_id in pending_thought_ids
    assert thought1_t2_id in pending_thought_ids
    assert thought2_t1_id not in pending_thought_ids # It's processing
    assert thought1_t3_id not in pending_thought_ids # Its task is not active

    # Check order: task1_id (priority 10) thought should come before task2_id (priority 5) thought
    assert pending_thoughts[0].thought_id == thought1_t1_id
    assert pending_thoughts[1].thought_id == thought1_t2_id


def test_deferral_report_mapping(initialized_db):
    now_iso = datetime.utcnow().isoformat()
    task = Task(task_id="task1", description="d", created_at=now_iso, updated_at=now_iso)
    thought = Thought(
        thought_id="th1",
        source_task_id="task1",
        thought_type="t",
        content="c",
        created_at=now_iso,
        updated_at=now_iso,
        round_created=0,
    )
    persistence.add_task(task)
    persistence.add_thought(thought)

    package = {"k": "v"}
    persistence.save_deferral_report_mapping("msg1", "task1", "th1", package)
    result = persistence.get_deferral_report_context("msg1")
    assert result == ("task1", "th1", package)

    assert persistence.get_deferral_report_context("missing") is None
