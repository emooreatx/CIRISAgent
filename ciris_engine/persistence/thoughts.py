import json
from datetime import datetime
from typing import List, Optional
from ciris_engine.persistence.db import get_db_connection
from ciris_engine.persistence.utils import map_row_to_thought
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
import logging

logger = logging.getLogger(__name__)

def get_thoughts_by_status(status: ThoughtStatus) -> List[Thought]:
    sql = "SELECT * FROM thoughts WHERE status = ? ORDER BY created_at ASC"
    thoughts = []
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (status.value,))
            rows = cursor.fetchall()
            for row in rows:
                thoughts.append(map_row_to_thought(row))
    except Exception as e:
        logger.exception(f"Failed to get thoughts with status {status.value}: {e}")
    return thoughts

def add_thought(thought: Thought) -> str:
    thought_dict = thought.model_dump(mode='json')
    sql = """
        INSERT INTO thoughts (thought_id, source_task_id, thought_type, status, created_at, updated_at,
                              round_number, content, context_json, ponder_count, ponder_notes_json,
                              parent_thought_id, final_action_json)
        VALUES (:thought_id, :source_task_id, :thought_type, :status, :created_at, :updated_at,
                :round_number, :content, :context, :ponder_count, :ponder_notes, :parent_thought_id, :final_action)
    """
    params = {
        **thought_dict,
        "status": thought.status.value,
        "context": json.dumps(thought_dict.get("context")) if thought_dict.get("context") is not None else None,
        "ponder_notes": json.dumps(thought_dict.get("ponder_notes")) if thought_dict.get("ponder_notes") is not None else None,
        "final_action": json.dumps(thought_dict.get("final_action")) if thought_dict.get("final_action") is not None else None,
    }
    try:
        with get_db_connection() as conn:
            conn.execute(sql, params)
            conn.commit()
        logger.info(f"Added thought ID {thought.thought_id} to database.")
        return thought.thought_id
    except Exception as e:
        logger.exception(f"Failed to add thought {thought.thought_id}: {e}")
        raise

def get_thought_by_id(thought_id: str) -> Optional[Thought]:
    sql = "SELECT * FROM thoughts WHERE thought_id = ?"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (thought_id,))
            row = cursor.fetchone()
            if row:
                return map_row_to_thought(row)
            return None
    except Exception as e:
        logger.exception(f"Failed to get thought {thought_id}: {e}")
        return None
