import pytest
import tempfile
import os
from ciris_engine.persistence import (
    add_task,
    get_task_by_id,
    update_task_status,
    task_exists,
    get_tasks_by_status,
    get_recent_completed_tasks,
    get_top_tasks,
    count_tasks,
    initialize_database,
)
from ciris_engine.schemas.agent_core_schemas_v1 import Task
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus
from datetime import datetime, timedelta, timezone

def temp_db_file():
    f = tempfile.NamedTemporaryFile(delete=False)
    f.close()
    return f.name

def make_task(task_id, status=TaskStatus.ACTIVE, priority=0, created_at=None, updated_at=None):
    now = datetime.now(timezone.utc).isoformat()
    return Task(
        task_id=str(task_id),
        description=f"desc-{task_id}",
        status=status,
        priority=int(priority),
        created_at=created_at or now,
        updated_at=updated_at or now
    )

def test_add_and_get_task():
    db_path = temp_db_file()
    try:
        initialize_database(db_path=db_path)
        t = make_task("t1", status=TaskStatus.PENDING)
        add_task(t, db_path=db_path)
        fetched = get_task_by_id("t1", db_path=db_path)
        assert fetched is not None
        assert fetched.task_id == "t1"
        assert fetched.status == TaskStatus.PENDING
    finally:
        os.unlink(db_path)

def test_update_task_status():
    db_path = temp_db_file()
    try:
        initialize_database(db_path=db_path)
        t = make_task("t2", status=TaskStatus.PENDING)
        add_task(t, db_path=db_path)
        ok = update_task_status("t2", TaskStatus.COMPLETED, db_path=db_path)
        assert ok
        updated = get_task_by_id("t2", db_path=db_path)
        assert updated.status == TaskStatus.COMPLETED
    finally:
        os.unlink(db_path)

def test_task_exists():
    db_path = temp_db_file()
    try:
        initialize_database(db_path=db_path)
        t = make_task("t3", status=TaskStatus.PENDING)
        add_task(t, db_path=db_path)
        assert task_exists("t3", db_path=db_path)
        assert not task_exists("notask", db_path=db_path)
    finally:
        os.unlink(db_path)

def test_get_tasks_by_status():
    db_path = temp_db_file()
    try:
        initialize_database(db_path=db_path)
        t1 = make_task("t4", status=TaskStatus.PENDING)
        t2 = make_task("t5", status=TaskStatus.ACTIVE)
        add_task(t1, db_path=db_path)
        add_task(t2, db_path=db_path)
        pending = get_tasks_by_status(TaskStatus.PENDING, db_path=db_path)
        active = get_tasks_by_status(TaskStatus.ACTIVE, db_path=db_path)
        assert any(t.task_id == "t4" for t in pending)
        assert any(t.task_id == "t5" for t in active)
    finally:
        os.unlink(db_path)

def test_get_recent_completed_tasks():
    db_path = temp_db_file()
    try:
        initialize_database(db_path=db_path)
        now = datetime.now(timezone.utc)
        t1 = make_task("t6", status=TaskStatus.COMPLETED, updated_at=(now - timedelta(days=1)).isoformat())
        t2 = make_task("t7", status=TaskStatus.COMPLETED, updated_at=now.isoformat())
        t3 = make_task("t8", status=TaskStatus.PENDING)
        add_task(t1, db_path=db_path)
        add_task(t2, db_path=db_path)
        add_task(t3, db_path=db_path)
        recent = get_recent_completed_tasks(limit=2, db_path=db_path)
        assert len(recent) == 2
        assert recent[0].task_id == "t7"
        assert recent[1].task_id == "t6"
    finally:
        os.unlink(db_path)

def test_get_top_tasks():
    db_path = temp_db_file()
    try:
        initialize_database(db_path=db_path)
        t1 = make_task("t9", priority=5, created_at="2025-05-27T00:00:00Z")
        t2 = make_task("t10", priority=10, created_at="2025-05-28T00:00:00Z")
        t3 = make_task("t11", priority=1, created_at="2025-05-26T00:00:00Z")
        add_task(t1, db_path=db_path)
        add_task(t2, db_path=db_path)
        add_task(t3, db_path=db_path)
        top = get_top_tasks(limit=2, db_path=db_path)
        assert len(top) == 2
        assert top[0].task_id == "t10"
        assert top[1].task_id == "t9"
    finally:
        os.unlink(db_path)

def test_count_tasks():
    db_path = temp_db_file()
    try:
        initialize_database(db_path=db_path)
        t1 = make_task("t12", status=TaskStatus.PENDING)
        t2 = make_task("t13", status=TaskStatus.PENDING)
        t3 = make_task("t14", status=TaskStatus.ACTIVE)
        add_task(t1, db_path=db_path)
        add_task(t2, db_path=db_path)
        add_task(t3, db_path=db_path)
        assert count_tasks(db_path=db_path) == 3
        assert count_tasks(TaskStatus.PENDING, db_path=db_path) == 2
        assert count_tasks(TaskStatus.ACTIVE, db_path=db_path) == 1
    finally:
        os.unlink(db_path)
