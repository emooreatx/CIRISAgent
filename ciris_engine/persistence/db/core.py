import sqlite3
import logging
from typing import Optional
from ciris_engine.config.config_manager import get_sqlite_db_full_path
from ciris_engine.schemas.db_tables_v1 import (
    tasks_table_v1,
    thoughts_table_v1,
    feedback_mappings_table_v1,
    graph_nodes_table_v1,
    graph_edges_table_v1,
    service_correlations_table_v1,
)
from .migration_runner import run_migrations

logger = logging.getLogger(__name__)

def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Establishes a connection to the SQLite database with foreign key support."""
    if db_path is None:
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

def get_graph_nodes_table_schema_sql() -> str:
    return graph_nodes_table_v1

def get_graph_edges_table_schema_sql() -> str:
    return graph_edges_table_v1

def get_service_correlations_table_schema_sql() -> str:
    return service_correlations_table_v1

def initialize_database(db_path: Optional[str] = None) -> None:
    """Apply pending migrations to initialize or update the database."""
    try:
        run_migrations(db_path)
        logger.info(
            f"Database migrations applied at {db_path or get_sqlite_db_full_path()}"
        )
    except sqlite3.Error as e:
        logger.exception(f"Database error during initialization: {e}")
        raise
