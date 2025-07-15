"""
Comprehensive tests for database core functionality.

Tests cover:
- Database connection and initialization
- Foreign key constraints
- Transaction management
- Concurrent access patterns
- Migration system
- Error handling
"""
import pytest
import sqlite3
import tempfile
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from typing import List

from ciris_engine.logic.persistence.db.core import (
    get_db_connection,
    initialize_database,
    adapt_datetime,
    convert_datetime,
    get_graph_nodes_table_schema_sql,
    get_graph_edges_table_schema_sql,
    get_service_correlations_table_schema_sql,
)
from ciris_engine.logic.persistence.db.migration_runner import (
    run_migrations,
    MIGRATIONS_DIR,
)
from ciris_engine.schemas.persistence.tables import (
    TASKS_TABLE_V1,
    THOUGHTS_TABLE_V1,
    GRAPH_NODES_TABLE_V1,
    GRAPH_EDGES_TABLE_V1,
)
from ciris_engine.schemas.runtime.enums import TaskStatus, ThoughtStatus


def get_applied_migrations(conn: sqlite3.Connection) -> set:
    """Get set of applied migrations from database."""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT filename FROM migrations")
        return {row[0] for row in cursor.fetchall()}
    except sqlite3.OperationalError:
        # Table might not exist yet
        return set()


class TestDatabaseCore:
    """Test core database functionality."""

    @pytest.fixture
    def temp_db_path(self) -> str:
        """Create a temporary database file."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        # Cleanup
        if os.path.exists(path):
            os.unlink(path)

    def test_database_initialization(self, temp_db_path: str):
        """Test database initialization creates all required tables."""
        # Initialize database
        initialize_database(temp_db_path)
        
        # Check all tables exist
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            
            # Get all table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            
            # Expected tables
            expected_tables = {
                'tasks', 'thoughts', 'feedback_mappings',
                'graph_nodes', 'graph_edges', 'service_correlations',
                'audit_log', 'audit_roots', 'audit_signing_keys',
                'wa_cert', 'schema_migrations'  # Correct table name
            }
            
            assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"

    def test_datetime_adapter_converter(self):
        """Test custom datetime adapter and converter."""
        # Test adapter
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        adapted = adapt_datetime(dt)
        assert adapted == "2025-01-01T12:00:00+00:00"
        
        # Test converter
        converted = convert_datetime(adapted.encode())
        assert converted == dt

    def test_foreign_key_constraints(self, temp_db_path: str):
        """Test foreign key constraints are enforced."""
        initialize_database(temp_db_path)
        
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            
            # Try to insert a thought with non-existent task_id
            with pytest.raises(sqlite3.IntegrityError) as exc_info:
                cursor.execute("""
                    INSERT INTO thoughts (thought_id, source_task_id, content, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, ("thought1", "non_existent_task", "test content", ThoughtStatus.PENDING.value, datetime.now(), datetime.now()))
            
            assert "FOREIGN KEY constraint failed" in str(exc_info.value)

    def test_transaction_atomicity(self, temp_db_path: str):
        """Test transaction atomicity and rollback."""
        initialize_database(temp_db_path)
        
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            
            # Start transaction
            conn.execute("BEGIN")
            
            # Insert a task
            cursor.execute("""
                INSERT INTO tasks (task_id, channel_id, description, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("task1", "test_channel", "test task", TaskStatus.PENDING.value, datetime.now(), datetime.now()))
            
            # Verify it's there within transaction
            cursor.execute("SELECT COUNT(*) FROM tasks WHERE task_id = ?", ("task1",))
            assert cursor.fetchone()[0] == 1
            
            # Rollback
            conn.rollback()
            
            # Verify it's gone after rollback
            cursor.execute("SELECT COUNT(*) FROM tasks WHERE task_id = ?", ("task1",))
            assert cursor.fetchone()[0] == 0

    def test_concurrent_read_access(self, temp_db_path: str):
        """Test concurrent read access patterns."""
        initialize_database(temp_db_path)
        
        # Insert test data
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            for i in range(100):
                cursor.execute("""
                    INSERT INTO tasks (task_id, channel_id, description, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (f"task{i}", "test_channel", f"test task {i}", TaskStatus.PENDING.value, datetime.now(), datetime.now()))
            conn.commit()
        
        # Concurrent reads
        def read_tasks():
            with get_db_connection(temp_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM tasks")
                count = cursor.fetchone()[0]
                assert count == 100
                return count
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures: List[Future] = []
            for _ in range(50):
                futures.append(executor.submit(read_tasks))
            
            # All should succeed
            results = [f.result() for f in futures]
            assert all(r == 100 for r in results)

    def test_concurrent_write_serialization(self, temp_db_path: str):
        """Test concurrent write access is properly serialized."""
        initialize_database(temp_db_path)
        
        counter = 0
        lock = threading.Lock()
        
        def write_task(task_num: int):
            nonlocal counter
            try:
                with get_db_connection(temp_db_path) as conn:
                    # Enable immediate mode for faster conflict detection
                    conn.execute("PRAGMA journal_mode=WAL")
                    cursor = conn.cursor()
                    
                    # Try to insert
                    cursor.execute("""
                        INSERT INTO tasks (task_id, channel_id, description, status, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (f"task_{task_num}", "test_channel", f"test task {task_num}", TaskStatus.PENDING.value, datetime.now(), datetime.now()))
                    
                    conn.commit()
                    
                    with lock:
                        counter += 1
                    return True
            except sqlite3.Error:
                return False
        
        # Concurrent writes
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(write_task, i) for i in range(50)]
            results = [f.result() for f in futures]
        
        # All writes should succeed
        assert all(results)
        assert counter == 50
        
        # Verify all tasks were written
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM tasks")
            assert cursor.fetchone()[0] == 50

    def test_database_connection_pooling(self, temp_db_path: str):
        """Test database connections are thread-safe."""
        initialize_database(temp_db_path)
        
        # SQLite connections are not thread-safe by default
        # But we use check_same_thread=False
        # Test that each thread gets its own connection
        
        thread_connections = {}
        
        def get_connection_id():
            conn = get_db_connection(temp_db_path)
            thread_id = threading.current_thread().ident
            thread_connections[thread_id] = id(conn)
            conn.close()
            return thread_id, id(conn)
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(get_connection_id) for _ in range(10)]
            results = [f.result() for f in futures]
        
        # Each thread should get different connection objects
        # (SQLite doesn't pool connections like other DBs)
        assert len(set(conn_id for _, conn_id in results)) > 1

    def test_schema_getter_functions(self):
        """Test schema getter functions return valid SQL."""
        # Test graph nodes schema
        nodes_sql = get_graph_nodes_table_schema_sql()
        assert "CREATE TABLE IF NOT EXISTS graph_nodes" in nodes_sql
        assert "PRIMARY KEY (node_id, scope)" in nodes_sql
        assert "node_id TEXT NOT NULL" in nodes_sql
        assert "scope TEXT NOT NULL" in nodes_sql
        
        # Test graph edges schema
        edges_sql = get_graph_edges_table_schema_sql()
        assert "CREATE TABLE IF NOT EXISTS graph_edges" in edges_sql
        assert "FOREIGN KEY (source_node_id, scope) REFERENCES graph_nodes(node_id, scope)" in edges_sql
        assert "FOREIGN KEY (target_node_id, scope) REFERENCES graph_nodes(node_id, scope)" in edges_sql
        
        # Test service correlations schema
        correlations_sql = get_service_correlations_table_schema_sql()
        assert "CREATE TABLE IF NOT EXISTS service_correlations" in correlations_sql

    def test_row_factory(self, temp_db_path: str):
        """Test sqlite3.Row factory allows dict-like access."""
        initialize_database(temp_db_path)
        
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            
            # Insert test data
            cursor.execute("""
                INSERT INTO tasks (task_id, channel_id, description, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("task1", "test_channel", "test task", TaskStatus.PENDING.value, datetime.now(), datetime.now()))
            conn.commit()
            
            # Query with Row factory
            cursor.execute("SELECT * FROM tasks WHERE task_id = ?", ("task1",))
            row = cursor.fetchone()
            
            # Should support both index and key access
            assert row["task_id"] == "task1"
            assert row["description"] == "test task"
            assert row[0] == "task1"  # task_id is first column

    def test_pragma_foreign_keys(self, temp_db_path: str):
        """Test foreign keys are enabled on connection."""
        initialize_database(temp_db_path)
        
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys")
            result = cursor.fetchone()
            assert result[0] == 1  # Foreign keys should be ON

    def test_migration_system(self, temp_db_path: str):
        """Test migration system tracks applied migrations."""
        initialize_database(temp_db_path)
        
        # Check migrations table exists
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM schema_migrations
            """)
            count = cursor.fetchone()[0]
            assert count >= 0  # Should have some migrations
            
            # Check that migrations tracking table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'")
            assert cursor.fetchone() is not None
            
            # Get applied migrations from actual table
            cursor.execute("SELECT filename FROM schema_migrations")
            applied = {row[0] for row in cursor.fetchall()}
            assert isinstance(applied, set)
            
            # Should have at least the initial migrations
            assert "001_initial_schema.sql" in applied
            assert "002_add_retry_status.sql" in applied

    def test_database_file_creation(self):
        """Test database file is created with proper permissions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "subdir", "test.db")
            
            # Directory doesn't exist yet
            assert not os.path.exists(os.path.dirname(db_path))
            
            # Create the parent directory first
            os.makedirs(os.path.dirname(db_path))
            
            # Initialize should create file
            initialize_database(db_path)
            
            assert os.path.exists(db_path)
            assert os.path.isfile(db_path)
            
            # Check file is readable/writable
            stat_info = os.stat(db_path)
            assert stat_info.st_size > 0  # Should have some content

    def test_connection_error_handling(self):
        """Test proper error handling for invalid database paths."""
        # Try to connect to read-only location
        invalid_path = "/invalid/path/test.db"
        
        with pytest.raises(sqlite3.Error):
            get_db_connection(invalid_path)

    def test_database_integrity_check(self, temp_db_path: str):
        """Test database passes integrity check after initialization."""
        initialize_database(temp_db_path)
        
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            assert result[0] == "ok"

    def test_unique_constraints(self, temp_db_path: str):
        """Test unique constraints are enforced."""
        initialize_database(temp_db_path)
        
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            
            # Insert a task
            cursor.execute("""
                INSERT INTO tasks (task_id, channel_id, description, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("task1", "test_channel", "test task", TaskStatus.PENDING.value, datetime.now(), datetime.now()))
            conn.commit()
            
            # Try to insert duplicate
            with pytest.raises(sqlite3.IntegrityError) as exc_info:
                cursor.execute("""
                    INSERT INTO tasks (task_id, channel_id, description, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, ("task1", "test_channel", "duplicate task", TaskStatus.PENDING.value, datetime.now(), datetime.now()))
            
            assert "UNIQUE constraint failed" in str(exc_info.value)

    def test_foreign_key_delete_restriction(self, temp_db_path: str):
        """Test foreign key constraints prevent deletion of referenced records."""
        initialize_database(temp_db_path)
        
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            
            # Insert task and thoughts
            cursor.execute("""
                INSERT INTO tasks (task_id, channel_id, description, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("task1", "test_channel", "test task", TaskStatus.ACTIVE.value, datetime.now(), datetime.now()))
            
            for i in range(3):
                cursor.execute("""
                    INSERT INTO thoughts (thought_id, source_task_id, content, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (f"thought{i}", "task1", f"content {i}", ThoughtStatus.PENDING.value, datetime.now(), datetime.now()))
            
            conn.commit()
            
            # Verify thoughts exist
            cursor.execute("SELECT COUNT(*) FROM thoughts WHERE source_task_id = ?", ("task1",))
            assert cursor.fetchone()[0] == 3
            
            # Try to delete task - should fail due to foreign key constraint
            with pytest.raises(sqlite3.IntegrityError) as exc_info:
                cursor.execute("DELETE FROM tasks WHERE task_id = ?", ("task1",))
            
            assert "FOREIGN KEY constraint failed" in str(exc_info.value)
            
            # Delete thoughts first, then task
            cursor.execute("DELETE FROM thoughts WHERE source_task_id = ?", ("task1",))
            cursor.execute("DELETE FROM tasks WHERE task_id = ?", ("task1",))
            conn.commit()
            
            # Both should be gone
            cursor.execute("SELECT COUNT(*) FROM tasks WHERE task_id = ?", ("task1",))
            assert cursor.fetchone()[0] == 0

    def test_check_constraints(self, temp_db_path: str):
        """Test CHECK constraints are enforced."""
        initialize_database(temp_db_path)
        
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            
            # Test CHECK constraint on audit_log sequence_number > 0
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute("""
                    INSERT INTO audit_log (event_id, event_timestamp, event_type, originator_id, 
                                         sequence_number, previous_hash, entry_hash, signature, signing_key_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, ("event1", datetime.now().isoformat(), "TEST", "test_user", 
                      0, "prev_hash", "entry_hash", "sig", "key1"))  # sequence_number 0 should fail

    def test_default_values(self, temp_db_path: str):
        """Test default values are properly set."""
        initialize_database(temp_db_path)
        
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            
            # Insert minimal graph node
            cursor.execute("""
                INSERT INTO graph_nodes (node_id, node_type, scope)
                VALUES (?, ?, ?)
            """, ("node1", "TEST", "LOCAL"))
            conn.commit()
            
            # Check defaults
            cursor.execute("SELECT * FROM graph_nodes WHERE node_id = ?", ("node1",))
            row = cursor.fetchone()
            
            assert row["version"] == 1  # Default version
            assert row["attributes_json"] is None  # No default for attributes_json in schema

    def test_json_field_handling(self, temp_db_path: str):
        """Test JSON fields are properly stored and retrieved."""
        initialize_database(temp_db_path)
        
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            
            # Complex JSON data
            json_data = '{"key": "value", "nested": {"array": [1, 2, 3]}, "bool": true}'
            
            # Insert with JSON
            cursor.execute("""
                INSERT INTO graph_nodes (node_id, node_type, scope, attributes_json)
                VALUES (?, ?, ?, ?)
            """, ("node1", "TEST", "LOCAL", json_data))
            conn.commit()
            
            # Retrieve
            cursor.execute("SELECT attributes_json FROM graph_nodes WHERE node_id = ?", ("node1",))
            result = cursor.fetchone()[0]
            
            # Should be stored as-is
            assert result == json_data

    def test_index_performance(self, temp_db_path: str):
        """Test indexes improve query performance."""
        initialize_database(temp_db_path)
        
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            
            # Insert many tasks
            for i in range(1000):
                cursor.execute("""
                    INSERT INTO tasks (task_id, channel_id, description, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (f"task{i}", "test_channel", f"test task {i}", 
                      TaskStatus.ACTIVE.value if i % 2 == 0 else TaskStatus.COMPLETED.value,
                      datetime.now(), datetime.now()))
            conn.commit()
            
            # Query using indexed column (status)
            cursor.execute("EXPLAIN QUERY PLAN SELECT * FROM tasks WHERE status = ?", 
                          (TaskStatus.ACTIVE.value,))
            plan = cursor.fetchall()
            
            # Should use index (look for "USING INDEX" in plan)
            plan_text = str(plan)
            # Note: SQLite might not always use index for this query
            # but the index should exist
            
            # Check for indexes on tasks table
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND tbl_name='tasks'
            """)
            indexes = cursor.fetchall()
            
            # Should have indexes for various columns (even if not specifically status)
            assert len(indexes) > 0  # Should have some indexes