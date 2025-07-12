import sqlite3
import logging
from typing import Optional
from datetime import datetime
from ciris_engine.logic.config.db_paths import get_sqlite_db_full_path
from ciris_engine.schemas.persistence.tables import (
    TASKS_TABLE_V1 as tasks_table_v1,
    THOUGHTS_TABLE_V1 as thoughts_table_v1,
    FEEDBACK_MAPPINGS_TABLE_V1 as feedback_mappings_table_v1,
    GRAPH_NODES_TABLE_V1 as graph_nodes_table_v1,
    GRAPH_EDGES_TABLE_V1 as graph_edges_table_v1,
    SERVICE_CORRELATIONS_TABLE_V1 as service_correlations_table_v1,
    AUDIT_LOG_TABLE_V1 as audit_log_table_v1,
    AUDIT_ROOTS_TABLE_V1 as audit_roots_table_v1,
    AUDIT_SIGNING_KEYS_TABLE_V1 as audit_signing_keys_table_v1,
    WA_CERT_TABLE_V1 as wa_cert_table_v1,
)
from .migration_runner import run_migrations

logger = logging.getLogger(__name__)


# Custom datetime adapter and converter for SQLite
def adapt_datetime(ts: datetime) -> str:
    """Convert datetime to ISO 8601 string."""
    return ts.isoformat()


def convert_datetime(val: bytes) -> datetime:
    """Convert ISO 8601 string back to datetime."""
    return datetime.fromisoformat(val.decode())


# Track if adapters have been registered
_adapters_registered = False


def _ensure_adapters_registered() -> None:
    """Register SQLite adapters if not already done."""
    global _adapters_registered
    if not _adapters_registered:
        sqlite3.register_adapter(datetime, adapt_datetime)
        sqlite3.register_converter("timestamp", convert_datetime)
        _adapters_registered = True


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Establishes a connection to the SQLite database with foreign key support."""
    # Ensure adapters are registered before creating connection
    _ensure_adapters_registered()
    
    if db_path is None:
        db_path = get_sqlite_db_full_path()
    conn = sqlite3.connect(db_path, check_same_thread=False, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

# Removed unused schema getter functions - only graph schemas are used

def get_graph_nodes_table_schema_sql() -> str:
    return graph_nodes_table_v1

def get_graph_edges_table_schema_sql() -> str:
    return graph_edges_table_v1

def get_service_correlations_table_schema_sql() -> str:
    return service_correlations_table_v1

def initialize_database(db_path: Optional[str] = None) -> None:
    """Initialize the database with base schema and apply migrations."""
    try:
        with get_db_connection(db_path) as conn:
            base_tables = [
                tasks_table_v1,
                thoughts_table_v1,
                feedback_mappings_table_v1,
                graph_nodes_table_v1,
                graph_edges_table_v1,
                service_correlations_table_v1,
                audit_log_table_v1,
                audit_roots_table_v1,
                audit_signing_keys_table_v1,
                wa_cert_table_v1,
            ]

            for table_sql in base_tables:
                conn.executescript(table_sql)

            conn.commit()

        run_migrations(db_path)

        logger.info(
            f"Database initialized at {db_path or get_sqlite_db_full_path()}"
        )
    except sqlite3.Error as e:
        logger.exception(f"Database error during initialization: {e}")
        raise
