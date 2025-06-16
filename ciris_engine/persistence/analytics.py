from ciris_engine.persistence.models import tasks as task_ops
from ciris_engine.persistence.models import thoughts as thought_ops
from ciris_engine.persistence import count_tasks
from ciris_engine.persistence import count_thoughts
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus
from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought
from typing import Optional, List


def get_pending_thoughts_for_active_tasks(limit: Optional[int] = None) -> List[Thought]:
    """Return all thoughts pending or processing for ACTIVE tasks."""
    active_tasks = task_ops.get_tasks_by_status(TaskStatus.ACTIVE)
    active_task_ids = {t.task_id for t in active_tasks}
    pending_thoughts = thought_ops.get_thoughts_by_status(ThoughtStatus.PENDING)
    processing_thoughts = thought_ops.get_thoughts_by_status(ThoughtStatus.PROCESSING)
    all_thoughts = pending_thoughts + processing_thoughts
    filtered = [th for th in all_thoughts if th.source_task_id in active_task_ids]
    if limit is not None:
        return filtered[:limit]
    return filtered


def count_pending_thoughts_for_active_tasks() -> int:
    """Return the count of thoughts pending or processing for ACTIVE tasks."""
    active_tasks = task_ops.get_tasks_by_status(TaskStatus.ACTIVE)
    active_task_ids = {t.task_id for t in active_tasks}
    pending_thoughts = thought_ops.get_thoughts_by_status(ThoughtStatus.PENDING)
    processing_thoughts = thought_ops.get_thoughts_by_status(ThoughtStatus.PROCESSING)
    all_thoughts = pending_thoughts + processing_thoughts
    filtered = [th for th in all_thoughts if th.source_task_id in active_task_ids]
    return len(filtered)


def count_active_tasks() -> int:
    """Count tasks with ACTIVE status."""
    return count_tasks(TaskStatus.ACTIVE)


def get_tasks_needing_seed_thought(limit: Optional[int] = None) -> List[Task]:
    """Get active tasks that don't yet have thoughts."""
    active_tasks = task_ops.get_tasks_by_status(TaskStatus.ACTIVE)
    tasks_needing_seed: List[Task] = []
    for task in active_tasks:
        thoughts = thought_ops.get_thoughts_by_task_id(task.task_id)
        if not thoughts:
            tasks_needing_seed.append(task)
    if limit:
        return tasks_needing_seed[:limit]
    return tasks_needing_seed


def pending_thoughts() -> bool:
    """Check if there are any pending thoughts."""
    return count_thoughts() > 0


def thought_exists_for(task_id: str) -> bool:
    """Check if any thoughts exist for the given task."""
    thoughts = thought_ops.get_thoughts_by_task_id(task_id)
    return len(thoughts) > 0


def count_thoughts_by_status(status: ThoughtStatus) -> int:
    """Count thoughts with the given status."""
    thoughts = thought_ops.get_thoughts_by_status(status)
    return len(thoughts)
