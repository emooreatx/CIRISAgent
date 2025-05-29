import pytest
from ciris_engine.schemas.context_schemas_v1 import SystemSnapshot, ThoughtContext


def test_system_snapshot_minimal():
    snap = SystemSnapshot()
    assert snap.current_task_details is None
    assert snap.current_thought_summary is None
    assert isinstance(snap.system_counts, dict)
    assert isinstance(snap.top_pending_tasks_summary, list)
    assert isinstance(snap.recently_completed_tasks_summary, list)
    assert snap.user_profiles is None


def test_system_snapshot_full():
    snap = SystemSnapshot(
        current_task_details={"task_id": "t1"},
        current_thought_summary={"thought_id": "th1"},
        system_counts={"total_tasks": 5},
        top_pending_tasks_summary=[{"task_id": "t2"}],
        recently_completed_tasks_summary=[{"task_id": "t3"}],
        user_profiles={"u1": {"name": "Alice"}},
        extra_field="extra"  # test extra allowed
    )
    assert snap.current_task_details["task_id"] == "t1"
    assert snap.current_thought_summary["thought_id"] == "th1"
    assert snap.system_counts["total_tasks"] == 5
    assert snap.top_pending_tasks_summary[0]["task_id"] == "t2"
    assert snap.recently_completed_tasks_summary[0]["task_id"] == "t3"
    assert snap.user_profiles["u1"]["name"] == "Alice"
    assert snap.extra_field == "extra"


def test_thought_context_minimal():
    snap = SystemSnapshot()
    ctx = ThoughtContext(system_snapshot=snap)
    assert isinstance(ctx.user_profiles, dict)
    assert isinstance(ctx.task_history, list)
    assert ctx.identity_context is None


def test_thought_context_full():
    snap = SystemSnapshot()
    ctx = ThoughtContext(
        system_snapshot=snap,
        user_profiles={"u2": {"name": "Bob"}},
        task_history=[{"task_id": "t4"}],
        identity_context="Agent identity string"
    )
    assert ctx.user_profiles["u2"]["name"] == "Bob"
    assert ctx.task_history[0]["task_id"] == "t4"
    assert ctx.identity_context == "Agent identity string"
