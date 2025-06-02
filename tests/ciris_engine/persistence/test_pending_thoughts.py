import pytest
from unittest.mock import patch, MagicMock
from ciris_engine.persistence import get_pending_thoughts_for_active_tasks, count_pending_thoughts_for_active_tasks
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, TaskStatus
from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought

def make_task(task_id, status=TaskStatus.ACTIVE):
    return Task(task_id=task_id, description="desc", status=status, priority=0, created_at="now", updated_at="now")

def make_thought(thought_id, source_task_id, status=ThoughtStatus.PENDING):
    return Thought(
        thought_id=thought_id,
        source_task_id=source_task_id,
        status=status,
        created_at="now",
        updated_at="now",
        content="content"
    )

def test_get_pending_thoughts_for_active_tasks_basic():
    # Only t1 is ACTIVE, so only thoughts for t1 should be returned
    tasks = [make_task("t1", status=TaskStatus.ACTIVE), make_task("t2", status=TaskStatus.COMPLETED)]
    thoughts = [
        make_thought("th1", "t1", status=ThoughtStatus.PENDING),
        make_thought("th3", "t1", status=ThoughtStatus.PROCESSING),
    ]
    def patched_get_thoughts_by_status(status):
        return [th for th in thoughts if th.status == status]
    with patch(
        "ciris_engine.persistence.models.tasks.get_tasks_by_status",
        return_value=tasks,
    ), patch(
        "ciris_engine.persistence.models.thoughts.get_thoughts_by_status",
        side_effect=patched_get_thoughts_by_status,
    ):
        result = get_pending_thoughts_for_active_tasks()
        assert len(result) == 2
        assert all(th.source_task_id == "t1" for th in result)


def test_count_pending_thoughts_for_active_tasks():
    tasks = [make_task("t1", status=TaskStatus.ACTIVE), make_task("t2", status=TaskStatus.COMPLETED)]
    thoughts = [
        make_thought("th1", "t1", status=ThoughtStatus.PENDING),
        make_thought("th3", "t1", status=ThoughtStatus.PROCESSING),
    ]
    def patched_get_thoughts_by_status(status):
        return [th for th in thoughts if th.status == status]
    with patch(
        "ciris_engine.persistence.models.tasks.get_tasks_by_status",
        return_value=tasks,
    ), patch(
        "ciris_engine.persistence.models.thoughts.get_thoughts_by_status",
        side_effect=patched_get_thoughts_by_status,
    ):
        count = count_pending_thoughts_for_active_tasks()
        assert count == 2

def test_get_pending_thoughts_for_active_tasks_limit():
    tasks = [make_task("t1")]
    thoughts = [make_thought(f"th{i}", "t1", status=ThoughtStatus.PENDING) for i in range(5)]
    with patch(
        "ciris_engine.persistence.models.tasks.get_tasks_by_status",
        return_value=tasks,
    ), patch(
        "ciris_engine.persistence.models.thoughts.get_thoughts_by_status",
        side_effect=lambda s: [th for th in thoughts if th.status == s],
    ):
        result = get_pending_thoughts_for_active_tasks(limit=3)
        assert len(result) == 3
