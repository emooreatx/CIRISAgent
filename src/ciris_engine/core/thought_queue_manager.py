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
                                     processing_context_json, dma_handler, processing_result_json)
            VALUES (:thought_id, :source_task_id, :thought_type_text, :content_json, :priority, :status_text,
                    :round_created, :round_processed, :created_at, :updated_at, :related_thought_id,
                    :processing_context_json, :dma_handler, :processing_result_json)
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

    def update_thought_status(self, thought_id: str, new_status: ThoughtStatus, round_processed: Optional[int] = None, processing_result: Optional[Dict[str, Any]] = None, ponder_notes: Optional[List[str]] = None) -> bool:
        sql = """
            UPDATE thoughts_table
            SET status = ?, updated_at = ?, round_processed = COALESCE(?, round_processed),
                processing_result_json = ?, ponder_notes_json = ?
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

    def _map_row_to_thought(self, row: sqlite3.Row) -> Thought:
        row_dict = dict(row) # Convert sqlite3.Row to a dict

        # Deserialize JSON fields
        for json_field_db, pydantic_field_model in [
            ("content_json", "content"),
            ("processing_context_json", "processing_context"),
            ("processing_result_json", "processing_result"),
            ("ponder_notes_json", "ponder_notes") # Added this line
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

        return Thought(**row_dict)


    def populate_round_queue(self, round_number: int, max_items: int = 10) -> None:
        self.current_round_queue.clear()
        self.current_round_number = round_number
        sql = """
            SELECT t.* FROM thoughts_table t
            INNER JOIN tasks_table tk ON t.source_task_id = tk.task_id
            WHERE t.status = ? AND tk.status = ?
            ORDER BY tk.priority DESC, t.priority DESC, t.created_at ASC
            LIMIT ?
        """
        try:
            with self._get_db_connection() as conn:
                # conn.row_factory = sqlite3.Row # Already set in _get_db_connection
                cursor = conn.cursor()
                # Using .value for Enums if they are Pydantic models holding the string
                pending_status_str = ThoughtStatus(status="pending").status
                active_task_status_str = TaskStatus(status="active").status
                cursor.execute(sql, (pending_status_str, active_task_status_str, max_items))
                pending_thoughts_rows = cursor.fetchall()

                for row in pending_thoughts_rows:
                    thought_db_instance = self._map_row_to_thought(row)
                    initial_ctx = thought_db_instance.processing_context if thought_db_instance.processing_context else {}
                    raw_input = str(thought_db_instance.content) if isinstance(thought_db_instance.content, str) else None

                    queue_item = ThoughtQueueItem.from_thought_db(
                        thought_db_instance,
                        raw_input=raw_input,
                        initial_ctx=initial_ctx
                    )
                    self.current_round_queue.append(queue_item)
                logging.info(f"Populated round {round_number} queue with {len(self.current_round_queue)} thoughts.")
        except sqlite3.Error as e:
            logging.error(f"Failed to populate round queue: {e}")

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

    def __repr__(self) -> str:
        return f"<ThoughtQueueManager db='{self.db_path}' queue_size={len(self.current_round_queue)} round={self.current_round_number}>"
