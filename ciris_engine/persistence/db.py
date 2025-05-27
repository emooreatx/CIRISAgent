import sqlite3
import logging
from ciris_engine.config.config_manager import get_sqlite_db_full_path
from ciris_engine.schemas.db_tables_v1 import tasks_table_v1, thoughts_table_v1, feedback_mappings_table_v1

logger = logging.getLogger(__name__)

def get_db_connection() -> sqlite3.Connection:
    """Establishes a connection to the SQLite database with foreign key support."""
    db_path = get_sqlite_db_full_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def get_task_table_schema_sql() -> str:
    return tasks_table_v1

def get_thought_table_schema_sql() -> str:
    return thoughts_table_v1

def get_feedback_mappings_table_schema_sql() -> str:
    return feedback_mappings_table_v1

def initialize_database():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(get_task_table_schema_sql())
            cursor.execute(get_thought_table_schema_sql())
            cursor.execute(get_feedback_mappings_table_schema_sql())
            conn.commit()
        logger.info(f"Database tables ensured at {get_sqlite_db_full_path()}")
    except sqlite3.Error as e:
        logger.exception(f"Database error during table creation: {e}")
        raise
