# src/ciris_engine/core/thought_queue_manager.py
import sqlite3
import json
import logging
import collections
from datetime import datetime
from typing import List, Optional, Any, Dict, Union
from pathlib import Path

from .data_schemas import Task, Thought, ThoughtQueueItem, TaskStatus, ThoughtStatus, ThoughtType
from .data_schemas import get_task_table_schema, get_thoughts_table_schema
from .config import SQLITE_DB_PATH

class ThoughtQueueManager:
    """
    Manages the persistent storage of tasks and thoughts in SQLite,
    and provides an in-memory queue (collections.deque) of ThoughtQueueItem
    instances for the current processing round.
    """

    def __init__(self, db_path: str = SQLITE_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_tables_if_not_exist()
        self.current_round_queue: collections.deque[ThoughtQueueItem] = collections.deque()
        self.current_round_number: int = 0

    def _get_db_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row # Set row_factory here for all connections from this manager
        return conn

    def _create_tables_if_not_exist(self):
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(get_task_table_schema())
                cursor.execute(get_thoughts_table_schema())
                conn.commit()
            logging.info(f"Database tables ensured at {self.db_path}")
        except sqlite3.Error as e:
            logging.error(f"Database error during table creation: {e}")
            raise

    def add_task(self, task: Task) -> str:
        task_dict = task.model_dump()
        sql = """
            INSERT INTO tasks_table (task_id, description, priority, status, created_at, updated_at, due_date, context_json, parent_goal_id)
            VALUES (:task_id, :description, :priority, :status_text, :created_at, :updated_at, :due_date, :context_json, :parent_goal_id)
        """
        params = {
            "task_id": task_dict["task_id"],
            "description": task_dict["description"],
            "priority": task_dict["priority"],
            "status_text": task_dict["status"]["status"],
            "created_at": task_dict["created_at"],
            "updated_at": task_dict["updated_at"],
            "due_date": task_dict["due_date"],
            "context_json": json.dumps(task_dict["context"]) if task_dict["context"] else None,
            "parent_goal_id": task_dict["parent_goal_id"],
        }
        try:
            with self._get_db_connection() as conn:
                conn.execute(sql, params)
                conn.commit()
            logging.info(f"Added task ID {task.task_id} to database.")
            return task.task_id
        except sqlite3.Error as e:
            logging.error(f"Failed to add task {task.task_id}: {e}")
            raise

    def add_thought(self, thought: Thought) -> str:
        thought_dict = thought.model_dump()
        sql = """
            INSERT INTO thoughts_table (thought_id, source_task_id, thought_type, content_json, priority, status,
                                     round_created, round_processed, created_at, updated_at, related_thought_id,
                                     processing_context_json, dma_handler, processing_result_json, ponder_count,
                                     context_json_text, queue_snapshot_text) -- Added new fields
            VALUES (:thought_id, :source_task_id, :thought_type_text, :content_json, :priority, :status_text,
                    :round_created, :round_processed, :created_at, :updated_at, :related_thought_id,
                    :processing_context_json, :dma_handler, :processing_result_json, :ponder_count,
                    :context_json_text, :queue_snapshot_text) -- Added new placeholders
        """
        params = {
            "thought_id": thought_dict["thought_id"],
            "source_task_id": thought_dict["source_task_id"],
            "thought_type_text": thought_dict["thought_type"]["type"],
            "content_json": json.dumps(thought_dict["content"]),
            "priority": thought_dict["priority"],
            "status_text": thought_dict["status"]["status"],
            "round_created": thought_dict["round_created"],
            "round_processed": thought_dict["round_processed"],
            "created_at": thought_dict["created_at"],
            "updated_at": thought_dict["updated_at"],
            "related_thought_id": thought_dict["related_thought_id"],
            "processing_context_json": json.dumps(thought_dict["processing_context"]) if thought_dict["processing_context"] else None,
            "dma_handler": thought_dict["dma_handler"],
            "processing_result_json": json.dumps(thought_dict["processing_result"]) if thought_dict["processing_result"] else None,
            "ponder_count": thought_dict["ponder_count"],
            "context_json_text": json.dumps(thought_dict["context_json"]) if thought_dict["context_json"] else None, # Added
            "queue_snapshot_text": json.dumps(thought_dict["queue_snapshot"]) if thought_dict["queue_snapshot"] else None, # Added
        }
        try:
            with self._get_db_connection() as conn:
                conn.execute(sql, params)
                conn.commit()
            logging.info(f"Added thought ID {thought.thought_id} to database.")
            return thought.thought_id
        except sqlite3.Error as e:
            logging.error(f"Failed to add thought {thought.thought_id}: {e}")
            raise

    def update_thought_status(self, thought_id: str, new_status: ThoughtStatus, round_processed: Optional[int] = None, processing_result: Optional[Dict[str, Any]] = None, ponder_notes: Optional[List[str]] = None, ponder_count: Optional[int] = None) -> bool:
        sql = """
            UPDATE thoughts_table
            SET status = ?, updated_at = ?, round_processed = COALESCE(?, round_processed),
                processing_result_json = ?, ponder_notes_json = ?, ponder_count = COALESCE(?, ponder_count)
            WHERE thought_id = ?
        """
        # For processing_result_json, if None is passed, it should store NULL.
        # If a dict is passed, it should be json.dumps'd.
        processing_result_db_val = json.dumps(processing_result) if processing_result is not None else None
        ponder_notes_db_val = json.dumps(ponder_notes) if ponder_notes is not None else None

        params = (
            new_status.status,
            datetime.utcnow(),
            round_processed, # This will be the NEW round it's intended for
            processing_result_db_val,
            ponder_notes_db_val, # Add this
            ponder_count, # Add this
            thought_id
        )
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute(sql, params)
                conn.commit()
                if cursor.rowcount > 0:
                    logging.info(f"Updated status of thought ID {thought_id} to {new_status.status}.")
                    return True
                logging.warning(f"Thought ID {thought_id} not found for status update.")
                return False
        except sqlite3.Error as e:
            logging.error(f"Failed to update thought status {thought_id}: {e}")
            return False

    def _map_row_to_task(self, row: sqlite3.Row) -> Task:
        """Helper to map a DB row to a Task Pydantic model."""
        row_dict = dict(row)
        if row_dict.get("context_json"):
            try:
                row_dict["context"] = json.loads(row_dict["context_json"])
            except json.JSONDecodeError:
                logging.warning(f"Failed to decode context_json for task {row_dict.get('task_id')}")
                row_dict["context"] = {}
        else:
            row_dict["context"] = {}
        
        if "context_json" in row_dict: # remove the _json key
            del row_dict["context_json"]

        status_val = row_dict.get("status")
        row_dict["status"] = TaskStatus(status=status_val if status_val else "pending")
        
        # Ensure all fields expected by Task model are present
        # Example: if 'parent_goal_id' might be missing from older DB rows
        if "parent_goal_id" not in row_dict:
            row_dict["parent_goal_id"] = None
        if "due_date" not in row_dict: # Pydantic handles Optional well, but good for awareness
            row_dict["due_date"] = None

        return Task(**row_dict)

    def _map_row_to_thought(self, row: sqlite3.Row) -> Thought:
        row_dict = dict(row) # Convert sqlite3.Row to a dict

        # Deserialize JSON fields
        for json_field_db, pydantic_field_model in [
            ("content_json", "content"),
            ("processing_context_json", "processing_context"),
            ("processing_result_json", "processing_result"),
            ("ponder_notes_json", "ponder_notes"),
            ("context_json_text", "context_json"), # Added for new field
            ("queue_snapshot_text", "queue_snapshot") # Added for new field
        ]:
            if row_dict.get(json_field_db):
                try:
                    row_dict[pydantic_field_model] = json.loads(row_dict[json_field_db])
                except json.JSONDecodeError:
                    logging.warning(f"Failed to decode JSON for field {json_field_db} in thought {row_dict.get('thought_id')}. Setting to None.")
                    row_dict[pydantic_field_model] = None
            else:
                # Ensure the key exists for Pydantic model, even if None
                row_dict[pydantic_field_model] = None if pydantic_field_model not in row_dict else row_dict.get(pydantic_field_model)

            if json_field_db in row_dict: # remove the _json key if it's different from model key
                 if json_field_db != pydantic_field_model:
                    del row_dict[json_field_db]


        # Handle nested Pydantic models for status and type
        # Ensure default values if keys are missing or None from DB
        status_val = row_dict.get("status")
        row_dict["status"] = ThoughtStatus(status=status_val if status_val else "pending")
        
        thought_type_val = row_dict.get("thought_type")
        row_dict["thought_type"] = ThoughtType(type=thought_type_val if thought_type_val else "thought")
        
        # Ensure all fields expected by Thought model are present, providing defaults if necessary
        # This is important if DB schema has fewer fields than Pydantic model due to evolution
        # For example, if 'dma_handler' is missing from row_dict, Pydantic might error
        # However, Pydantic's default_factory or Optional should handle missing fields if schema is aligned.
        # For safety, one might iterate through Thought.__fields__ and ensure keys exist.
        if "ponder_count" not in row_dict: # Default ponder_count if not in DB row
            row_dict["ponder_count"] = 0

        return Thought(**row_dict)


    def count_pending_thoughts(self) -> int:
        """Counts thoughts with status 'pending'."""
        sql = "SELECT COUNT(*) FROM thoughts_table WHERE status = ?"
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (ThoughtStatus(status="pending").status,))
                count = cursor.fetchone()[0]
                return count if count is not None else 0
        except sqlite3.Error as e:
            logging.error(f"Failed to count pending thoughts: {e}")
            return 0 # Return 0 on error to avoid breaking queue snapshot

    def count_active_tasks(self) -> int:
        """Counts tasks with status 'active'."""
        sql = "SELECT COUNT(*) FROM tasks_table WHERE status = ?"
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (TaskStatus(status="active").status,))
                count = cursor.fetchone()[0]
                return count if count is not None else 0
        except sqlite3.Error as e:
            logging.error(f"Failed to count active tasks: {e}")
            return 0

    def populate_round_queue(self, round_number: int, max_items: int = 10) -> None:
        self.current_round_queue.clear()
        self.current_round_number = round_number

        # Step 1: Identify active tasks that need a seed thought
        # A task needs a seed thought if it's 'active' and has no 'pending' or 'processing' thoughts.
        # This query is a bit complex: find tasks that DON'T have such thoughts.
        sql_tasks_needing_seed = """
            SELECT tk.*
            FROM tasks_table tk
            WHERE tk.status = ? AND
                  NOT EXISTS (
                      SELECT 1
                      FROM thoughts_table th
                      WHERE th.source_task_id = tk.task_id AND (th.status = ? OR th.status = ? OR th.status = ?))
            ORDER BY tk.priority DESC, tk.created_at ASC
            LIMIT ?;
        """
        # Note: The LIMIT here applies to tasks needing seed thoughts.
        # We might want a separate limit for this vs. existing pending thoughts.
        # For now, let's assume max_items is an overall target for the queue.

        newly_seeded_thoughts_count = 0
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                active_task_status = TaskStatus(status="active").status
                pending_thought_status = ThoughtStatus(status="pending").status
                processing_thought_status = ThoughtStatus(status="processing").status
                completed_thought_status = ThoughtStatus(status="completed").status

                # Fetch tasks that need seeding
                # Limit to max_items for now, can be adjusted
                cursor.execute(sql_tasks_needing_seed, (active_task_status, pending_thought_status, processing_thought_status, completed_thought_status, max_items))
                tasks_to_seed_rows = cursor.fetchall()

                for task_row in tasks_to_seed_rows:
                    if len(self.current_round_queue) >= max_items:
                        break  # Stop if queue is full

                    task_instance = self._map_row_to_task(task_row)

                    # Prepare context for the new seed thought
                    seed_thought_context_json = {
                        "environment": task_instance.context.get("environment", "unknown_env_from_task"),
                        "channel": task_instance.context.get("channel", "unknown_channel_from_task"),
                        "agent_name": task_instance.context.get("agent_name", "CIRIS Bot")  # Default agent name
                    }

                    # Prepare queue snapshot
                    # These counts are at the moment of seed thought creation
                    queue_snapshot = {
                        "pending_thoughts_at_creation": self.count_pending_thoughts(),
                        "active_tasks_at_creation": self.count_active_tasks()
                    }

                    # Determine content for the seed thought
                    # Prefer "initial_input_content" from task's context if available
                    thought_content = task_instance.context.get("initial_input_content", task_instance.description)
                    if not thought_content:  # Fallback if both are empty/None
                        thought_content = "Task requires initial processing."
                        logging.warning(f"Task {task_instance.task_id} has no initial_input_content or description for seed thought.")

                    new_seed_thought = Thought(
                        source_task_id=task_instance.task_id,
                        thought_type=ThoughtType(type="seed_task_thought"),
                        content=thought_content,
                        priority=task_instance.priority,
                        status=ThoughtStatus(status="pending"),
                        round_created=self.current_round_number,
                        processing_context=task_instance.context,  # Copy task's full context here
                        context_json=seed_thought_context_json,
                        queue_snapshot=queue_snapshot,
                        ponder_count=0
                    )

                    try:
                        self.add_thought(new_seed_thought)  # Persist the new seed thought
                        # Create ThoughtQueueItem and add to in-memory queue
                        initial_ctx_for_queue_item = new_seed_thought.processing_context if new_seed_thought.processing_context else {}
                        raw_input_for_queue_item = str(new_seed_thought.content)  # Assuming content is suitable as raw_input

                        queue_item = ThoughtQueueItem.from_thought_db(
                            new_seed_thought,
                            raw_input=raw_input_for_queue_item,
                            initial_ctx=initial_ctx_for_queue_item
                        )
                        self.current_round_queue.append(queue_item)
                        newly_seeded_thoughts_count += 1
                        logging.info(f"Created and enqueued seed thought {new_seed_thought.thought_id} for task {task_instance.task_id}.")
                    except Exception as e_add_thought:
                        logging.error(f"Failed to add/enqueue seed thought for task {task_instance.task_id}: {e_add_thought}")

        except sqlite3.Error as e:
            logging.error(f"Failed to query tasks needing seed thoughts: {e}")

        # Step 2: Populate with existing pending thoughts (if queue not full)
        remaining_capacity = max_items - len(self.current_round_queue)
        existing_pending_thoughts_count = 0
        if remaining_capacity > 0:
            sql_existing_pending = """
            SELECT t.* FROM thoughts_table t
            INNER JOIN tasks_table tk ON t.source_task_id = tk.task_id
            WHERE t.status = ? AND tk.status = ?
            AND t.status != 'completed'
            ORDER BY tk.priority DESC, t.priority DESC, t.created_at ASC
            LIMIT ?
            """
            try:
                with self._get_db_connection() as conn:
                    cursor = conn.cursor()
                    pending_status_str = ThoughtStatus(status="pending").status
                    active_task_status_str = TaskStatus(status="active").status
                    cursor.execute(sql_existing_pending, (pending_status_str, active_task_status_str, remaining_capacity))
                    pending_thoughts_rows = cursor.fetchall()

                    for row in pending_thoughts_rows:
                        thought_db_instance = self._map_row_to_thought(row)
                        # Avoid re-adding if it was just seeded (though SQL for tasks_needing_seed should prevent this)
                        if any(item.thought_id == thought_db_instance.thought_id for item in self.current_round_queue):
                            continue

                        initial_ctx = thought_db_instance.processing_context if thought_db_instance.processing_context else {}
                        raw_input = str(thought_db_instance.content) if isinstance(thought_db_instance.content, str) else None

                        queue_item = ThoughtQueueItem.from_thought_db(
                            thought_db_instance,
                            raw_input=raw_input,
                            initial_ctx=initial_ctx
                        )
                        self.current_round_queue.append(queue_item)
                        existing_pending_thoughts_count +=1
            except sqlite3.Error as e:
                logging.error(f"Failed to populate round queue with existing pending thoughts: {e}")
        
        logging.info(f"Populated round {round_number} queue: {newly_seeded_thoughts_count} new seed thoughts, {existing_pending_thoughts_count} existing pending. Total: {len(self.current_round_queue)}.")


    def get_next_thought_from_queue(self) -> Optional[ThoughtQueueItem]:
        if self.current_round_queue:
            thought_item = self.current_round_queue.popleft()
            logging.info(f"Dequeued thought ID {thought_item.thought_id} for processing.")
            return thought_item
        return None

    def get_thought_by_id(self, thought_id: str) -> Optional[Thought]:
        sql = "SELECT * FROM thoughts_table WHERE thought_id = ?"
        try:
            with self._get_db_connection() as conn:
                # conn.row_factory = sqlite3.Row # Already set
                cursor = conn.cursor()
                cursor.execute(sql, (thought_id,))
                row = cursor.fetchone()
                if row:
                    return self._map_row_to_thought(row)
                return None
        except sqlite3.Error as e:
            logging.error(f"Failed to get thought {thought_id}: {e}")
            return None

    def get_task_by_id(self, task_id: str) -> Optional[Task]:
        sql = "SELECT * FROM tasks_table WHERE task_id = ?"
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (task_id,))
                row = cursor.fetchone()
                if row:
                    return self._map_row_to_task(row) # Use the existing helper
                return None
        except sqlite3.Error as e:
            logging.error(f"Failed to get task {task_id}: {e}")
            return None

    def get_task_description_by_id(self, task_id: str) -> Optional[str]:
        task = self.get_task_by_id(task_id)
        return task.description if task else None

    def get_top_priority_tasks(self, limit: int = 3) -> List[Dict[str, Any]]:
        """Fetches top N active tasks, ordered by priority then creation time."""
        sql = """
            SELECT task_id, description, priority, status
            FROM tasks_table
            WHERE status = ?
            ORDER BY priority DESC, created_at ASC
            LIMIT ?
        """
        tasks_summary = []
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                active_status = TaskStatus(status="active").status
                cursor.execute(sql, (active_status, limit))
                rows = cursor.fetchall()
                for row in rows:
                    tasks_summary.append({
                        "task_id": row["task_id"],
                        "description": row["description"],
                        "priority": row["priority"],
                        "status": row["status"]
                    })
            return tasks_summary
        except sqlite3.Error as e:
            logging.error(f"Failed to get top priority tasks: {e}")
            return []

    def update_task_status(self, task_id: str, new_status: TaskStatus) -> bool:
        """Updates the status of a specific task in the database."""
        sql = """
            UPDATE tasks_table
            SET status = ?, updated_at = ?
            WHERE task_id = ?
        """
        params = (
            new_status.status,
            datetime.utcnow(),
            task_id
        )
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute(sql, params)
                conn.commit()
                if cursor.rowcount > 0:
                    logging.info(f"Updated status of task ID {task_id} to {new_status.status}.")
                    return True
                logging.warning(f"Task ID {task_id} not found for status update.")
                return False
        except sqlite3.Error as e:
            logging.error(f"Failed to update task status for {task_id}: {e}")
            return False

    def __repr__(self) -> str:
        return f"<ThoughtQueueManager db='{self.db_path}' queue_size={len(self.current_round_queue)} round={self.current_round_number}>"
