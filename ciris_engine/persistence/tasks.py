import json
from datetime import datetime
from typing import List, Optional
from ciris_engine.persistence.db import get_db_connection
from ciris_engine.persistence.utils import map_row_to_task
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus
from ciris_engine.schemas.agent_core_schemas_v1 import Task
import logging

logger = logging.getLogger(__name__)

def get_tasks_by_status(status: TaskStatus) -> List[Task]:
    sql = "SELECT * FROM tasks WHERE status = ? ORDER BY created_at ASC"
    tasks = []
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (status.value,))
            rows = cursor.fetchall()
            for row in rows:
                tasks.append(map_row_to_task(row))
    except Exception as e:
        logger.exception(f"Failed to get tasks with status {status.value}: {e}")
    return tasks

def get_all_tasks() -> List[Task]:
    sql = "SELECT * FROM tasks ORDER BY created_at ASC"
    tasks = []
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            for row in rows:
                tasks.append(map_row_to_task(row))
    except Exception as e:
        logger.exception(f"Failed to get all tasks: {e}")
    return tasks

def add_task(task: Task) -> str:
    task_dict = task.model_dump(mode='json')
    sql = """
        INSERT INTO tasks (task_id, description, status, priority, created_at, updated_at,
                           parent_task_id, context_json, outcome_json)
        VALUES (:task_id, :description, :status, :priority, :created_at, :updated_at,
                :parent_task_id, :context, :outcome)
    """
    params = {
        **task_dict,
        "status": task.status.value,
        "context": json.dumps(task_dict.get("context")) if task_dict.get("context") is not None else None,
        "outcome": json.dumps(task_dict.get("outcome")) if task_dict.get("outcome") is not None else None,
    }
    try:
        with get_db_connection() as conn:
            conn.execute(sql, params)
            conn.commit()
        logger.info(f"Added task ID {task.task_id} to database.")
        return task.task_id
    except Exception as e:
        logger.exception(f"Failed to add task {task.task_id}: {e}")
        raise

def get_task_by_id(task_id: str) -> Optional[Task]:
    sql = "SELECT * FROM tasks WHERE task_id = ?"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (task_id,))
            row = cursor.fetchone()
            if row:
                return map_row_to_task(row)
            return None
    except Exception as e:
        logger.exception(f"Failed to get task {task_id}: {e}")
        return None

def update_task_status(task_id: str, new_status: TaskStatus) -> bool:
    sql = "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?"
    params = (new_status.value, datetime.utcnow().isoformat(), task_id)
    try:
        with get_db_connection() as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            if cursor.rowcount > 0:
                logger.info(f"Updated status of task ID {task_id} to {new_status.value}.")
                return True
            logger.warning(f"Task ID {task_id} not found for status update.")
            return False
    except Exception as e:
        logger.exception(f"Failed to update task status for {task_id}: {e}")
        return False

def task_exists(task_id: str) -> bool:
    return get_task_by_id(task_id) is not None

def get_recent_completed_tasks(limit: int = 10) -> list[Task]:
    """Return the most recent completed tasks, sorted by updated_at descending, as Task objects."""
    tasks = get_all_tasks()  # Already returns List[Task]
    completed = [t for t in tasks if getattr(t, 'status', None) == TaskStatus.COMPLETED]
    completed_sorted = sorted(completed, key=lambda t: getattr(t, 'updated_at', ''), reverse=True)
    return completed_sorted[:limit]

def get_top_tasks(limit: int = 10) -> list[Task]:
    """Return the top tasks by priority, then by created_at ascending, as Task objects."""
    tasks = get_all_tasks()  # Already returns List[Task]
    sorted_tasks = sorted(tasks, key=lambda t: (-getattr(t, 'priority', 0), getattr(t, 'created_at', '')))
    return sorted_tasks[:limit]

def count_tasks(status: Optional[TaskStatus] = None) -> int:
    """
    Return the count of tasks.
    If status is provided, counts tasks with that specific status.
    Otherwise, counts all tasks.
    """
    # This approach fetches all tasks then filters.
    # For performance on large datasets, a direct SQL COUNT query would be better.
    # However, sticking to the existing pattern of get_all_tasks() for now.
    tasks = get_all_tasks()
    if status:
        return sum(1 for t in tasks if getattr(t, 'status', None) == status)
    return len(tasks)
