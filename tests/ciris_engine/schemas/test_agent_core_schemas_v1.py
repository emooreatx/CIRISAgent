import pytest
from ciris_engine.schemas import agent_core_schemas_v1 as acs
from ciris_engine.schemas import foundational_schemas_v1 as fs
from pydantic import ValidationError
from datetime import datetime, timezone

def utcnow_iso():
    return datetime.now(timezone.utc).isoformat() + 'Z'

# Test Task model

def test_task_minimal():
    now = datetime.now(timezone.utc).isoformat()
    t = acs.Task(
        task_id="t1",
        description="Test task",
        created_at=now,
        updated_at=now,
    )
    assert t.status == fs.TaskStatus.PENDING
    assert t.priority == 0
    assert t.context == {}
    assert t.outcome == {}
    assert t.parent_task_id is None


def test_task_required_fields():
    with pytest.raises(ValidationError):
        acs.Task(description="desc", created_at=utcnow_iso(), updated_at=utcnow_iso())

# Test Thought model

def test_thought_minimal():
    th = acs.Thought(
        thought_id="th1",
        source_task_id="t1",
        content="A thought",
        created_at=utcnow_iso(),
        updated_at=utcnow_iso(),
    )
    assert th.status == fs.ThoughtStatus.PENDING
    assert th.thought_type == "standard"
    assert th.context == {}
    assert th.ponder_count == 0
    assert th.ponder_notes is None
    assert th.parent_thought_id is None
    assert th.final_action == {}


def test_thought_required_fields():
    with pytest.raises(ValidationError):
        acs.Thought(source_task_id="t1", content="Missing id", created_at=utcnow_iso(), updated_at=utcnow_iso())

# Test round_number default

def test_thought_round_number_default():
    th = acs.Thought(
        thought_id="th2",
        source_task_id="t1",
        content="Another thought",
        created_at=utcnow_iso(),
        updated_at=utcnow_iso(),
    )
    assert th.round_number == 0
