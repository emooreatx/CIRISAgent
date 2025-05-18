import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pathlib import Path

# Configuration and Schemas
from .config_manager import get_sqlite_db_full_path
from .foundational_schemas import TaskStatus, ThoughtStatus
from .agent_core_schemas import Task, Thought

# --- Database Initialization ---

def _get_db_connection() -> sqlite3.Connection:
    """Establishes a connection to the SQLite database."""
    db_path = get_sqlite_db_full_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row # Use row_factory for dict-like access
    # Enable foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def _get_task_table_schema_sql() -> str:
    """Returns the SQL statement to create the tasks table based on the NEW Task schema."""
    # Note: Pydantic types map to SQLite types (e.g., str -> TEXT, int -> INTEGER, bool -> INTEGER, Optional[T] -> T NULL)
    # Timestamps are stored as TEXT in ISO8601 format.
    # Dict/List fields (context, parameters, outcome, dependencies) are stored as JSON TEXT.
    return """
    CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        task_ual TEXT UNIQUE, -- Added field
        description TEXT NOT NULL,
        status TEXT NOT NULL, -- References TaskStatus enum values
        priority INTEGER DEFAULT 0,
        created_at TEXT NOT NULL, -- ISO8601 timestamp
        updated_at TEXT NOT NULL, -- ISO8601 timestamp
        due_date TEXT, -- ISO8601 timestamp, Added field
        assigned_agent_ual TEXT, -- Added field
        originator_id TEXT, -- Added field
        parent_goal_id TEXT, -- Added field
        parameters_json TEXT, -- Added field (stored as JSON)
        context_json TEXT, -- Stored as JSON
        outcome_json TEXT, -- Added field (stored as JSON)
        dependencies_json TEXT -- Added field (stored as JSON list of UALs)
    );
    """

def _get_thought_table_schema_sql() -> str:
    """Returns the SQL statement to create the thoughts table based on the NEW Thought schema."""
    # Note: final_action_result stored as JSON TEXT.
    # ponder_notes stored as JSON TEXT list.
    return """
    CREATE TABLE IF NOT EXISTS thoughts (
        thought_id TEXT PRIMARY KEY,
        source_task_id TEXT NOT NULL,
        thought_type TEXT NOT NULL,
        status TEXT NOT NULL, -- References ThoughtStatus enum values
        created_at TEXT NOT NULL, -- ISO8601 timestamp
        updated_at TEXT NOT NULL, -- ISO8601 timestamp
        round_created INTEGER NOT NULL, -- Added field
        round_processed INTEGER, -- Added field
        priority INTEGER DEFAULT 0, -- Added field
        content TEXT NOT NULL, -- Stored as TEXT (was JSON in old schema)
        processing_context_json TEXT, -- Stored as JSON
        depth INTEGER DEFAULT 0,
        ponder_count INTEGER DEFAULT 0,
        ponder_notes_json TEXT, -- Stored as JSON list
        related_thought_id TEXT,
        final_action_result_json TEXT, -- Added field (stored as JSON)
        FOREIGN KEY (source_task_id) REFERENCES tasks(task_id)
            ON DELETE CASCADE,
        FOREIGN KEY (related_thought_id) REFERENCES thoughts(thought_id)
            ON DELETE SET NULL
    );
    """

def initialize_database():
    """Creates the database tables if they don't exist."""
    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(_get_task_table_schema_sql())
            cursor.execute(_get_thought_table_schema_sql())
            conn.commit()
        logging.info(f"Database tables ensured at {get_sqlite_db_full_path()}")
    except sqlite3.Error as e:
        logging.exception(f"Database error during table creation: {e}") # Use exception for stack trace
        raise

# --- Data Mapping Helpers ---

def _map_row_to_task(row: sqlite3.Row) -> Task:
    """Maps a database row to a Task Pydantic model."""
    row_dict = dict(row)

    # Deserialize JSON fields
    for json_field, model_field in [
        ("parameters_json", "parameters"),
        ("context_json", "context"),
        ("outcome_json", "outcome"),
        ("dependencies_json", "dependencies"),
    ]:
        if row_dict.get(json_field):
            try:
                row_dict[model_field] = json.loads(row_dict[json_field])
            except json.JSONDecodeError:
                logging.warning(f"Failed to decode {json_field} for task {row_dict.get('task_id')}")
                row_dict[model_field] = None # Or appropriate default like {} or []
        else:
            # Ensure key exists if field is not Optional in model, or set default
             row_dict[model_field] = None # Task fields are Optional or have defaults

        # Remove the original _json key if it differs from the model field name
        if json_field != model_field and json_field in row_dict:
            del row_dict[json_field]

    # Ensure status is valid enum member (or handle potential invalid data from DB)
    try:
        row_dict["status"] = TaskStatus(row_dict["status"])
    except ValueError:
        logging.warning(f"Invalid status value '{row_dict['status']}' found for task {row_dict.get('task_id')}. Defaulting to PENDING.")
        row_dict["status"] = TaskStatus.PENDING

    # Pydantic should handle Optional fields being None from DB
    return Task(**row_dict)

def _map_row_to_thought(row: sqlite3.Row) -> Thought:
    """Maps a database row to a Thought Pydantic model."""
    row_dict = dict(row)

    # Deserialize JSON fields
    for json_field, model_field in [
        ("processing_context_json", "processing_context"),
        ("ponder_notes_json", "ponder_notes"),
        ("final_action_result_json", "final_action_result"),
    ]:
        if row_dict.get(json_field):
            try:
                row_dict[model_field] = json.loads(row_dict[json_field])
            except json.JSONDecodeError:
                logging.warning(f"Failed to decode {json_field} for thought {row_dict.get('thought_id')}")
                row_dict[model_field] = None # Or appropriate default
        else:
             row_dict[model_field] = None # Fields are Optional or have defaults

        if json_field != model_field and json_field in row_dict:
            del row_dict[json_field]

    # Ensure status is valid enum member
    try:
        row_dict["status"] = ThoughtStatus(row_dict["status"])
    except ValueError:
        logging.warning(f"Invalid status value '{row_dict['status']}' found for thought {row_dict.get('thought_id')}. Defaulting to PENDING.")
        row_dict["status"] = ThoughtStatus.PENDING

    # Pydantic should handle Optional fields and defaults
    return Thought(**row_dict)


# --- Task Operations ---

def add_task(task: Task) -> str:
    """Adds a new task to the database."""
    # Use model_dump for serialization compatible with DB schema
    task_dict = task.model_dump(mode='json') # Get dict suitable for JSON/DB
    
    sql = """
        INSERT INTO tasks (task_id, task_ual, description, status, priority, created_at, updated_at,
                           due_date, assigned_agent_ual, originator_id, parent_goal_id,
                           parameters_json, context_json, outcome_json, dependencies_json)
        VALUES (:task_id, :task_ual, :description, :status, :priority, :created_at, :updated_at,
                :due_date, :assigned_agent_ual, :originator_id, :parent_goal_id,
                :parameters, :context, :outcome, :dependencies)
    """
    # Prepare params, ensuring complex types are JSON strings
    params = {
        **task_dict, # Spread the dictionary
        "status": task.status.value, # Use enum value
        "parameters": json.dumps(task_dict.get("parameters")) if task_dict.get("parameters") is not None else None,
        "context": json.dumps(task_dict.get("context")) if task_dict.get("context") is not None else None,
        "outcome": json.dumps(task_dict.get("outcome")) if task_dict.get("outcome") is not None else None,
        "dependencies": json.dumps(task_dict.get("dependencies")) if task_dict.get("dependencies") is not None else None,
    }

    try:
        with _get_db_connection() as conn:
            conn.execute(sql, params)
            conn.commit()
        logging.info(f"Added task ID {task.task_id} to database.")
        return task.task_id
    except sqlite3.Error as e:
        logging.exception(f"Failed to add task {task.task_id}: {e}")
        raise

def get_task_by_id(task_id: str) -> Optional[Task]:
    """Retrieves a task by its ID."""
    sql = "SELECT * FROM tasks WHERE task_id = ?"
    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (task_id,))
            row = cursor.fetchone()
            if row:
                return _map_row_to_task(row)
            return None
    except sqlite3.Error as e:
        logging.exception(f"Failed to get task {task_id}: {e}")
        return None

def update_task_status(task_id: str, new_status: TaskStatus) -> bool:
    """Updates the status of a specific task."""
    sql = "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?"
    params = (new_status.value, datetime.utcnow().isoformat(), task_id)
    try:
        with _get_db_connection() as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            if cursor.rowcount > 0:
                logging.info(f"Updated status of task ID {task_id} to {new_status.value}.")
                return True
            logging.warning(f"Task ID {task_id} not found for status update.")
            return False
    except sqlite3.Error as e:
        logging.exception(f"Failed to update task status for {task_id}: {e}")
        return False

def task_exists(task_id: str) -> bool:
    """Checks if a task with the given ID exists."""
    return get_task_by_id(task_id) is not None

def count_active_tasks() -> int:
    """Counts tasks with status 'active'."""
    sql = "SELECT COUNT(*) FROM tasks WHERE status = ?"
    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (TaskStatus.ACTIVE.value,))
            count = cursor.fetchone()[0]
            return count if count is not None else 0
    except sqlite3.Error as e:
        logging.exception(f"Failed to count active tasks: {e}")
        return 0

def get_pending_tasks_for_activation(limit: int) -> List[Task]:
    """Retrieves pending tasks, ordered by priority and creation date, up to a limit."""
    sql = """
        SELECT * FROM tasks
        WHERE status = ?
        ORDER BY priority DESC, created_at ASC
        LIMIT ?
    """
    tasks = []
    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            pending_status = TaskStatus.PENDING.value
            cursor.execute(sql, (pending_status, limit))
            rows = cursor.fetchall()
            for row in rows:
                tasks.append(_map_row_to_task(row))
            logging.debug(f"Retrieved {len(tasks)} pending tasks for activation (limit: {limit}).")
    except sqlite3.Error as e:
        logging.exception(f"Failed to get pending tasks for activation: {e}")
    return tasks

def get_active_tasks_by_priority(limit: int) -> List[Task]:
    """Retrieves active tasks, ordered by priority and creation date, up to a limit."""
    sql = """
        SELECT * FROM tasks
        WHERE status = ?
        ORDER BY priority DESC, created_at ASC
        LIMIT ?
    """
    tasks = []
    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            active_status = TaskStatus.ACTIVE.value
            cursor.execute(sql, (active_status, limit))
            rows = cursor.fetchall()
            for row in rows:
                tasks.append(_map_row_to_task(row))
            logging.debug(f"Retrieved {len(tasks)} active tasks by priority (limit: {limit}).")
    except sqlite3.Error as e:
        logging.exception(f"Failed to get active tasks by priority: {e}")
    return tasks

# --- Thought Operations ---

def add_thought(thought: Thought) -> str:
    """Adds a new thought to the database."""
    thought_dict = thought.model_dump(mode='json')
    sql = """
        INSERT INTO thoughts (thought_id, source_task_id, thought_type, status, created_at, updated_at,
                              round_created, round_processed, priority, content, processing_context_json,
                              depth, ponder_count, ponder_notes_json, related_thought_id, final_action_result_json)
        VALUES (:thought_id, :source_task_id, :thought_type, :status, :created_at, :updated_at,
                :round_created, :round_processed, :priority, :content, :processing_context,
                :depth, :ponder_count, :ponder_notes, :related_thought_id, :final_action_result)
    """
    params = {
        **thought_dict,
        "status": thought.status.value,
        "processing_context": json.dumps(thought_dict.get("processing_context")) if thought_dict.get("processing_context") is not None else None,
        "ponder_notes": json.dumps(thought_dict.get("ponder_notes")) if thought_dict.get("ponder_notes") is not None else None,
        "final_action_result": json.dumps(thought_dict.get("final_action_result")) if thought_dict.get("final_action_result") is not None else None,
    }
    try:
        with _get_db_connection() as conn:
            conn.execute(sql, params)
            conn.commit()
        logging.info(f"Added thought ID {thought.thought_id} to database.")
        return thought.thought_id
    except sqlite3.Error as e:
        logging.exception(f"Failed to add thought {thought.thought_id}: {e}")
        raise

def get_thought_by_id(thought_id: str) -> Optional[Thought]:
    """Retrieves a thought by its ID."""
    sql = "SELECT * FROM thoughts WHERE thought_id = ?"
    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (thought_id,))
            row = cursor.fetchone()
            if row:
                return _map_row_to_thought(row)
            return None
    except sqlite3.Error as e:
        logging.exception(f"Failed to get thought {thought_id}: {e}")
        return None

def update_thought_status(
    thought_id: str,
    new_status: ThoughtStatus,
    round_processed: Optional[int] = None,
    final_action_result: Optional[Dict[str, Any]] = None, # Changed from processing_result
    ponder_notes: Optional[List[str]] = None,
    ponder_count: Optional[int] = None
) -> bool:
    """Updates the status and optionally other fields of a specific thought."""
    # Build the SET part dynamically? Or just update all optional fields passed.
    sql = """
        UPDATE thoughts
        SET status = ?, updated_at = ?, round_processed = COALESCE(?, round_processed),
            final_action_result_json = ?, ponder_notes_json = ?, ponder_count = COALESCE(?, ponder_count)
        WHERE thought_id = ?
    """
    final_action_result_db_val = json.dumps(final_action_result) if final_action_result is not None else None
    ponder_notes_db_val = json.dumps(ponder_notes) if ponder_notes is not None else None

    params = (
        new_status.value,
        datetime.utcnow().isoformat(),
        round_processed,
        final_action_result_db_val,
        ponder_notes_db_val,
        ponder_count,
        thought_id
    )
    try:
        with _get_db_connection() as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            if cursor.rowcount > 0:
                logging.info(f"Updated status of thought ID {thought_id} to {new_status.value}.")
                return True
            logging.warning(f"Thought ID {thought_id} not found for status update.")
            return False
    except sqlite3.Error as e:
        logging.exception(f"Failed to update thought status {thought_id}: {e}")
        return False

def count_pending_thoughts() -> int:
    """Counts thoughts with status 'pending'."""
    sql = "SELECT COUNT(*) FROM thoughts WHERE status = ?"
    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (ThoughtStatus.PENDING.value,))
            count = cursor.fetchone()[0]
            return count if count is not None else 0
    except sqlite3.Error as e:
        logging.exception(f"Failed to count pending thoughts: {e}")
        return 0

def count_thoughts_by_status(status: ThoughtStatus) -> int:
    """Counts thoughts with a specific status."""
    sql = "SELECT COUNT(*) FROM thoughts WHERE status = ?"
    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (status.value,))
            count = cursor.fetchone()[0]
            return count if count is not None else 0
    except sqlite3.Error as e:
        logging.exception(f"Failed to count thoughts with status {status.value}: {e}")
        return 0

# --- Functions needed by Workflow Coordinator ---

def get_tasks_needing_seed_thought(limit: int) -> List[Task]:
    """Finds active tasks that do not have any non-completed thoughts."""
    # A task needs a seed thought if it's 'active' and has no thoughts
    # OR all its existing thoughts are 'completed', 'failed', 'deferred', or 'rejected'.
    sql = """
        SELECT tk.*
        FROM tasks tk
        WHERE tk.status = ? AND
              NOT EXISTS (
                  SELECT 1
                  FROM thoughts th
                  WHERE th.source_task_id = tk.task_id AND
                        th.status NOT IN (?, ?, ?, ?)
              )
        ORDER BY tk.priority DESC, tk.created_at ASC
        LIMIT ?;
    """
    tasks = []
    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            active_status = TaskStatus.ACTIVE.value
            # Statuses that mean a thought is 'done' or doesn't need seeding over
            terminal_statuses = (
                ThoughtStatus.COMPLETED.value,
                ThoughtStatus.FAILED.value,
                ThoughtStatus.DEFERRED.value,
                ThoughtStatus.REJECTED.value
            )
            # Find tasks where no thoughts exist with non-terminal statuses
            cursor.execute(sql, (active_status, *terminal_statuses, limit))
            rows = cursor.fetchall()
            for row in rows:
                tasks.append(_map_row_to_task(row))
    except sqlite3.Error as e:
        logging.exception(f"Failed to query tasks needing seed thoughts: {e}")
    return tasks

def get_pending_thoughts_for_active_tasks(limit: int) -> List[Thought]:
    """Gets pending thoughts for active tasks, ordered by priority."""
    sql = """
        SELECT t.* FROM thoughts t
        INNER JOIN tasks tk ON t.source_task_id = tk.task_id
        WHERE t.status = ? AND tk.status = ?
        ORDER BY tk.priority DESC, t.priority DESC, t.created_at ASC
        LIMIT ?
    """
    thoughts = []
    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            pending_status = ThoughtStatus.PENDING.value
            active_task_status = TaskStatus.ACTIVE.value
            cursor.execute(sql, (pending_status, active_task_status, limit))
            rows = cursor.fetchall()
            for row in rows:
                thoughts.append(_map_row_to_thought(row))
    except sqlite3.Error as e:
        logging.exception(f"Failed to get pending thoughts for active tasks: {e}")
    return thoughts

# --- Other Utility Functions (Example) ---

def get_task_description_by_id(task_id: str) -> Optional[str]:
    """Gets only the description of a task by ID."""
    task = get_task_by_id(task_id)
    return task.description if task else None

def count_tasks(status: Optional[TaskStatus] = None) -> int:
    """Counts tasks, optionally filtered by status."""
    sql = "SELECT COUNT(*) FROM tasks"
    params: tuple[Any, ...] = ()
    if status:
        sql += " WHERE status = ?"
        params = (status.value,)
    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            count = cursor.fetchone()[0]
            return count if count is not None else 0
    except sqlite3.Error as e:
        logging.exception(f"Failed to count tasks: {e}")
        return 0

def count_thoughts(status: Optional[ThoughtStatus] = None) -> int:
    """Counts thoughts, optionally filtered by status."""
    sql = "SELECT COUNT(*) FROM thoughts"
    params: tuple[Any, ...] = ()
    if status:
        sql += " WHERE status = ?"
        params = (status.value,)
    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            count = cursor.fetchone()[0]
            return count if count is not None else 0
    except sqlite3.Error as e:
        logging.exception(f"Failed to count thoughts: {e}")
        return 0

def pending_thoughts() -> bool:
    """Returns True if any pending thoughts exist."""
    return count_pending_thoughts() > 0

def thought_exists_for(task_id: str) -> bool:
    """Checks if a pending or processing thought exists for the given task."""
    sql = (
        "SELECT 1 FROM thoughts WHERE source_task_id = ? AND status IN (?, ?) LIMIT 1"
    )
    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                sql,
                (
                    task_id,
                    ThoughtStatus.PENDING.value,
                    ThoughtStatus.PROCESSING.value,
                ),
            )
            return cursor.fetchone() is not None
    except sqlite3.Error as e:
        logging.exception(f"Failed to check thought existence for {task_id}: {e}")
        return False

def get_top_tasks(limit: int) -> List[Task]:
    """Alias for get_active_tasks_by_priority to match API."""
    return get_active_tasks_by_priority(limit)

# Ensure database is initialized when module is loaded (optional)
# initialize_database()
