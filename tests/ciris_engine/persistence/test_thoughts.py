import os
import tempfile
import pytest
from ciris_engine.persistence.db import initialize_database
from ciris_engine.persistence.models.thoughts import (
    get_thoughts_by_status,
    add_thought,
    get_thought_by_id,
    get_thoughts_by_task_id,
    delete_thoughts_by_ids,
    count_thoughts,
    update_thought_status,
    pydantic_to_dict,
)
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, Task
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, TaskStatus
from ciris_engine.persistence.models.tasks import add_task
from datetime import datetime, timezone

def temp_db_file():
    f = tempfile.NamedTemporaryFile(delete=False)
    f.close()
    return f.name

def make_thought(thought_id, source_task_id="task1", status=ThoughtStatus.PENDING, created_at=None, updated_at=None):
    now = datetime.now(timezone.utc).isoformat()
    return Thought(
        thought_id=thought_id,
        source_task_id=source_task_id,
        thought_type="test",
        status=status,
        created_at=created_at or now,
        updated_at=updated_at or now,
        round_number=1,
        content="test content",
        context={},
        ponder_count=0,
        ponder_notes=None,
        parent_thought_id=None,
        final_action={}
    )

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

def test_add_and_get_thought():
    db_path = temp_db_file()
    try:
        initialize_database(db_path=db_path)
        add_task(make_task("task1"), db_path=db_path)
        th = make_thought("th1")
        add_thought(th, db_path=db_path)
        fetched = get_thought_by_id("th1", db_path=db_path)
        assert fetched is not None
        assert fetched.thought_id == "th1"
    finally:
        os.unlink(db_path)

def test_get_thoughts_by_status():
    db_path = temp_db_file()
    try:
        initialize_database(db_path=db_path)
        add_task(make_task("task1"), db_path=db_path)
        th1 = make_thought("th2", status=ThoughtStatus.PENDING)
        th2 = make_thought("th3", status=ThoughtStatus.PROCESSING)
        add_thought(th1, db_path=db_path)
        add_thought(th2, db_path=db_path)
        pending = get_thoughts_by_status(ThoughtStatus.PENDING, db_path=db_path)
        assert any(th.thought_id == "th2" for th in pending)
    finally:
        os.unlink(db_path)

def test_get_thoughts_by_task_id():
    db_path = temp_db_file()
    try:
        initialize_database(db_path=db_path)
        add_task(make_task("taskX"), db_path=db_path)
        add_task(make_task("taskY"), db_path=db_path)
        th1 = make_thought("th4", source_task_id="taskX")
        th2 = make_thought("th5", source_task_id="taskY")
        add_thought(th1, db_path=db_path)
        add_thought(th2, db_path=db_path)
        thoughts = get_thoughts_by_task_id("taskX", db_path=db_path)
        assert len(thoughts) == 1
        assert thoughts[0].thought_id == "th4"
    finally:
        os.unlink(db_path)

def test_delete_thoughts_by_ids():
    db_path = temp_db_file()
    try:
        initialize_database(db_path=db_path)
        add_task(make_task("task1"), db_path=db_path)
        th1 = make_thought("th6")
        th2 = make_thought("th7")
        add_thought(th1, db_path=db_path)
        add_thought(th2, db_path=db_path)
        deleted = delete_thoughts_by_ids(["th6", "th7"], db_path=db_path)
        assert deleted == 2
        assert get_thought_by_id("th6", db_path=db_path) is None
    finally:
        os.unlink(db_path)

def test_count_thoughts():
    db_path = temp_db_file()
    try:
        initialize_database(db_path=db_path)
        add_task(make_task("task1"), db_path=db_path)
        th1 = make_thought("th8", status=ThoughtStatus.PENDING)
        th2 = make_thought("th9", status=ThoughtStatus.PROCESSING)
        th3 = make_thought("th10", status=ThoughtStatus.COMPLETED)
        add_thought(th1, db_path=db_path)
        add_thought(th2, db_path=db_path)
        add_thought(th3, db_path=db_path)
        count = count_thoughts(db_path=db_path)
        assert count == 2
    finally:
        os.unlink(db_path)

def test_update_thought_status():
    db_path = temp_db_file()
    try:
        initialize_database(db_path=db_path)
        add_task(make_task("task1"), db_path=db_path)
        th = make_thought("th11", status=ThoughtStatus.PENDING)
        add_thought(th, db_path=db_path)
        update_thought_status("th11", ThoughtStatus.COMPLETED, db_path=db_path)
        updated = get_thought_by_id("th11", db_path=db_path)
        assert updated.status == ThoughtStatus.COMPLETED
    finally:
        os.unlink(db_path)

def test_pydantic_to_dict():
    th = make_thought("th12")
    d = pydantic_to_dict(th)
    assert isinstance(d, dict)
    assert d["thought_id"] == "th12"
