# Remove the wildcard import from .db
# from .db import *  # <-- Remove or comment out this line

# Import only what you need from db.py
from .db import (
    get_db_connection,
    initialize_database,
    get_tasks_older_than,  # <-- Added to re-export for external use
    get_thoughts_older_than,  # <-- Added to re-export for external use
)
from .tasks import (
    update_task_status,
    task_exists,
    add_task,
    get_all_tasks,
    get_task_by_id,
    get_tasks_by_status,
    get_recent_completed_tasks,
    get_top_tasks,
    get_pending_tasks_for_activation,
    count_tasks,
    delete_tasks_by_ids,
)
from .thoughts import (
    add_thought,
    get_thought_by_id,
    update_thought_status,
    get_thoughts_by_status,
    get_thoughts_by_task_id,
    count_thoughts,
    delete_thoughts_by_ids,
)
from .deferral import save_deferral_report_mapping, get_deferral_report_context
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus


def get_pending_thoughts_for_active_tasks(limit=None):
    """Return all thoughts with status PENDING or PROCESSING for ACTIVE tasks. Optionally limit the number returned."""
    active_tasks = get_tasks_by_status(TaskStatus.ACTIVE)
    active_task_ids = {t.task_id for t in active_tasks}
    pending_thoughts = get_thoughts_by_status(ThoughtStatus.PENDING)
    processing_thoughts = get_thoughts_by_status(ThoughtStatus.PROCESSING)
    all_thoughts = pending_thoughts + processing_thoughts
    filtered = [th for th in all_thoughts if th.source_task_id in active_task_ids]
    if limit is not None:
        return filtered[:limit]
    return filtered


def count_pending_thoughts_for_active_tasks():
    """Return the count of thoughts with status PENDING or PROCESSING for ACTIVE tasks."""
    active_tasks = get_tasks_by_status(TaskStatus.ACTIVE)
    active_task_ids = {t.task_id for t in active_tasks}
    pending_thoughts = get_thoughts_by_status(ThoughtStatus.PENDING)
    processing_thoughts = get_thoughts_by_status(ThoughtStatus.PROCESSING)
    all_thoughts = pending_thoughts + processing_thoughts
    filtered = [th for th in all_thoughts if th.source_task_id in active_task_ids]
    return len(filtered)


def count_active_tasks():
    """Count tasks with ACTIVE status."""
    return count_tasks(TaskStatus.ACTIVE)


def get_tasks_needing_seed_thought(limit=None):
    """Get active tasks that don't have any thoughts yet."""
    active_tasks = get_tasks_by_status(TaskStatus.ACTIVE)
    tasks_needing_seed = []
    
    for task in active_tasks:
        thoughts = get_thoughts_by_task_id(task.task_id)
        if not thoughts:
            tasks_needing_seed.append(task)
    
    if limit:
        return tasks_needing_seed[:limit]
    return tasks_needing_seed


def pending_thoughts():
    """Check if there are any pending thoughts."""
    return count_thoughts() > 0


def thought_exists_for(task_id):
    """Check if any thoughts exist for the given task."""
    thoughts = get_thoughts_by_task_id(task_id)
    return len(thoughts) > 0


def count_thoughts_by_status(status):
    """Count thoughts with the given status. Accepts a TaskStatus enum value."""
    thoughts = get_thoughts_by_status(status)
    return len(thoughts)

from .maintenance import DatabaseMaintenanceService
