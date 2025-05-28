from .db import *
from .tasks import update_task_status, task_exists, add_task, get_all_tasks, get_recent_completed_tasks, get_top_tasks, get_task_by_id, count_tasks
from .thoughts import add_thought, get_thought_by_id, get_thoughts_by_status, get_thoughts_by_task_id, delete_thoughts_by_ids, update_thought_status, count_thoughts
from .deferral import save_deferral_report_mapping, get_deferral_report_context


def get_pending_thoughts_for_active_tasks(limit=None):
    """Return all thoughts with status PENDING or PROCESSING for ACTIVE tasks. Optionally limit the number returned."""
    active_tasks = get_tasks_by_status("active")
    active_task_ids = {t.task_id for t in active_tasks}
    pending_thoughts = get_thoughts_by_status("pending")
    processing_thoughts = get_thoughts_by_status("processing")
    all_thoughts = pending_thoughts + processing_thoughts
    filtered = [th for th in all_thoughts if th.source_task_id in active_task_ids]
    if limit is not None:
        return filtered[:limit]
    return filtered


def count_pending_thoughts_for_active_tasks():
    """Return the count of thoughts with status PENDING or PROCESSING for ACTIVE tasks."""
    active_tasks = get_tasks_by_status("active")
    active_task_ids = {t.task_id for t in active_tasks}
    pending_thoughts = get_thoughts_by_status("pending")
    processing_thoughts = get_thoughts_by_status("processing")
    all_thoughts = pending_thoughts + processing_thoughts
    filtered = [th for th in all_thoughts if th.source_task_id in active_task_ids]
    return len(filtered)
