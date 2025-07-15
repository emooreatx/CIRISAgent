"""
Comprehensive tests for database transaction management.

Tests cover:
- Transaction atomicity (ACID properties)
- Nested transactions (savepoints)
- Concurrent transaction handling
- Deadlock detection and recovery
- Transaction isolation levels
- Long-running transactions
"""
import pytest
import sqlite3
import tempfile
import os
import time
import threading
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from ciris_engine.logic.persistence.db.core import (
    get_db_connection,
    initialize_database,
)
from ciris_engine.logic.persistence.models import (
    add_task,
    add_thought,
    update_task_status,
    get_task_by_id,
    get_thought_by_id,
)
from ciris_engine.schemas.runtime.enums import TaskStatus, ThoughtStatus
# Remove unused imports - Task and Thought schemas


@dataclass
class TransactionResult:
    """Result of a transaction attempt."""
    success: bool
    error: Optional[str] = None
    duration_ms: float = 0.0
    retry_count: int = 0


class TestTransactionAtomicity:
    """Test ACID transaction properties."""

    @pytest.fixture
    def temp_db_path(self) -> str:
        """Create a temporary database file."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)

    def test_atomicity_all_or_nothing(self, temp_db_path: str):
        """Test that transactions are atomic - all operations succeed or all fail."""
        initialize_database(temp_db_path)
        
        with get_db_connection(temp_db_path) as conn:
            try:
                # Start explicit transaction
                conn.execute("BEGIN IMMEDIATE")
                cursor = conn.cursor()
                
                # Insert task
                cursor.execute("""
                    INSERT INTO tasks (task_id, channel_id, description, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, ("task1", "test_channel", "test task", TaskStatus.ACTIVE.value, datetime.now(timezone.utc), datetime.now(timezone.utc)))
                
                # Insert thought for task
                cursor.execute("""
                    INSERT INTO thoughts (thought_id, source_task_id, content, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, ("thought1", "task1", "test thought", ThoughtStatus.PENDING.value, datetime.now(timezone.utc), datetime.now(timezone.utc)))
                
                # Force an error - duplicate primary key
                cursor.execute("""
                    INSERT INTO tasks (task_id, channel_id, description, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, ("task1", "test_channel", "duplicate", TaskStatus.ACTIVE.value, datetime.now(timezone.utc), datetime.now(timezone.utc)))
                
                conn.commit()
                
            except sqlite3.IntegrityError:
                conn.rollback()
        
        # Verify nothing was inserted
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM tasks")
            assert cursor.fetchone()[0] == 0
            
            cursor.execute("SELECT COUNT(*) FROM thoughts")
            assert cursor.fetchone()[0] == 0

    def test_consistency_foreign_keys(self, temp_db_path: str):
        """Test that transactions maintain referential integrity."""
        initialize_database(temp_db_path)
        
        # Try to insert thought without parent task
        with get_db_connection(temp_db_path) as conn:
            try:
                conn.execute("BEGIN")
                cursor = conn.cursor()
                
                # This should fail due to foreign key constraint
                cursor.execute("""
                    INSERT INTO thoughts (thought_id, source_task_id, content, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, ("thought1", "nonexistent_task", "orphan thought", 
                      ThoughtStatus.PENDING.value, datetime.now(timezone.utc), datetime.now(timezone.utc)))
                
                conn.commit()
                assert False, "Should have raised IntegrityError"
                
            except sqlite3.IntegrityError:
                conn.rollback()
                # This is expected

    def test_isolation_read_uncommitted(self, temp_db_path: str):
        """Test transaction isolation levels."""
        initialize_database(temp_db_path)
        
        # Insert initial data
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tasks (task_id, channel_id, description, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("task1", "test_channel", "initial", TaskStatus.PENDING.value, datetime.now(timezone.utc), datetime.now(timezone.utc)))
            conn.commit()
        
        # Connection 1: Start transaction and update
        conn1 = get_db_connection(temp_db_path)
        conn1.execute("BEGIN")
        cursor1 = conn1.cursor()
        cursor1.execute("""
            UPDATE tasks SET status = ? WHERE task_id = ?
        """, (TaskStatus.ACTIVE.value, "task1"))
        
        # Connection 2: Try to read (should see old value due to isolation)
        conn2 = get_db_connection(temp_db_path)
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT status FROM tasks WHERE task_id = ?", ("task1",))
        status = cursor2.fetchone()[0]
        
        # Should still see PENDING since conn1 hasn't committed
        assert status == TaskStatus.PENDING.value
        
        # Commit conn1
        conn1.commit()
        
        # Now conn2 should see the update
        cursor2.execute("SELECT status FROM tasks WHERE task_id = ?", ("task1",))
        status = cursor2.fetchone()[0]
        assert status == TaskStatus.ACTIVE.value
        
        conn1.close()
        conn2.close()

    def test_durability_after_commit(self, temp_db_path: str):
        """Test that committed transactions persist."""
        initialize_database(temp_db_path)
        
        # Insert and commit
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tasks (task_id, channel_id, description, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("task1", "test_channel", "durable task", TaskStatus.ACTIVE.value, datetime.now(timezone.utc), datetime.now(timezone.utc)))
            conn.commit()
        
        # Close connection completely
        del conn
        
        # Reopen and verify data persists
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT description FROM tasks WHERE task_id = ?", ("task1",))
            result = cursor.fetchone()
            assert result[0] == "durable task"


class TestSavepoints:
    """Test nested transactions using savepoints."""

    @pytest.fixture
    def temp_db_path(self) -> str:
        """Create a temporary database file."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)

    def test_savepoint_rollback(self, temp_db_path: str):
        """Test rolling back to a savepoint."""
        initialize_database(temp_db_path)
        
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            
            # Start transaction
            conn.execute("BEGIN")
            
            # Insert first task
            cursor.execute("""
                INSERT INTO tasks (task_id, channel_id, description, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("task1", "test_channel", "first task", TaskStatus.PENDING.value, datetime.now(timezone.utc), datetime.now(timezone.utc)))
            
            # Create savepoint
            conn.execute("SAVEPOINT sp1")
            
            # Insert second task
            cursor.execute("""
                INSERT INTO tasks (task_id, channel_id, description, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("task2", "test_channel", "second task", TaskStatus.PENDING.value, datetime.now(timezone.utc), datetime.now(timezone.utc)))
            
            # Rollback to savepoint
            conn.execute("ROLLBACK TO sp1")
            
            # Commit transaction
            conn.commit()
            
            # Verify only first task exists
            cursor.execute("SELECT COUNT(*) FROM tasks")
            assert cursor.fetchone()[0] == 1
            
            cursor.execute("SELECT task_id FROM tasks")
            assert cursor.fetchone()[0] == "task1"

    def test_nested_savepoints(self, temp_db_path: str):
        """Test multiple nested savepoints."""
        initialize_database(temp_db_path)
        
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            
            conn.execute("BEGIN")
            
            # Level 0: Insert task
            cursor.execute("""
                INSERT INTO tasks (task_id, channel_id, description, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("task1", "test_channel", "level 0", TaskStatus.ACTIVE.value, datetime.now(timezone.utc), datetime.now(timezone.utc)))
            
            # Level 1: Savepoint
            conn.execute("SAVEPOINT sp1")
            cursor.execute("""
                INSERT INTO thoughts (thought_id, source_task_id, content, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("thought1", "task1", "level 1", ThoughtStatus.PENDING.value, datetime.now(timezone.utc), datetime.now(timezone.utc)))
            
            # Level 2: Nested savepoint
            conn.execute("SAVEPOINT sp2")
            cursor.execute("""
                INSERT INTO thoughts (thought_id, source_task_id, content, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("thought2", "task1", "level 2", ThoughtStatus.PENDING.value, datetime.now(timezone.utc), datetime.now(timezone.utc)))
            
            # Rollback to sp2 (no effect)
            conn.execute("ROLLBACK TO sp2")
            
            # Rollback to sp1 (removes thought1 and thought2)
            conn.execute("ROLLBACK TO sp1")
            
            # Release savepoint and commit
            conn.execute("RELEASE sp1")
            conn.commit()
            
            # Verify only task exists, no thoughts
            cursor.execute("SELECT COUNT(*) FROM tasks")
            assert cursor.fetchone()[0] == 1
            
            cursor.execute("SELECT COUNT(*) FROM thoughts")
            assert cursor.fetchone()[0] == 0


class TestConcurrentTransactions:
    """Test concurrent transaction handling."""

    @pytest.fixture
    def temp_db_path(self) -> str:
        """Create a temporary database file."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)

    def test_concurrent_inserts(self, temp_db_path: str):
        """Test multiple threads inserting concurrently."""
        initialize_database(temp_db_path)
        
        def insert_task(task_num: int) -> TransactionResult:
            start_time = time.time()
            try:
                with get_db_connection(temp_db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO tasks (task_id, channel_id, description, status, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (f"task_{task_num}", "test_channel", f"concurrent task {task_num}", 
                          TaskStatus.PENDING.value, datetime.now(timezone.utc), datetime.now(timezone.utc)))
                    conn.commit()
                
                duration_ms = (time.time() - start_time) * 1000
                return TransactionResult(success=True, duration_ms=duration_ms)
            
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                return TransactionResult(success=False, error=str(e), duration_ms=duration_ms)
        
        # Run concurrent inserts
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(insert_task, i) for i in range(50)]
            results = [f.result() for f in as_completed(futures)]
        
        # All should succeed
        successes = [r for r in results if r.success]
        assert len(successes) == 50
        
        # Verify all tasks were inserted
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM tasks")
            assert cursor.fetchone()[0] == 50

    def test_concurrent_updates_same_row(self, temp_db_path: str):
        """Test concurrent updates to the same row."""
        initialize_database(temp_db_path)
        
        # Insert initial task
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tasks (task_id, channel_id, description, status, created_at, updated_at, priority)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ("shared_task", "test_channel", "shared task", TaskStatus.PENDING.value, 
                  datetime.now(timezone.utc), datetime.now(timezone.utc), 0))
            conn.commit()
        
        def increment_priority(thread_id: int) -> TransactionResult:
            start_time = time.time()
            retry_count = 0
            max_retries = 5
            
            while retry_count < max_retries:
                try:
                    with get_db_connection(temp_db_path) as conn:
                        conn.execute("BEGIN IMMEDIATE")  # Lock database
                        cursor = conn.cursor()
                        
                        # Read current priority
                        cursor.execute("SELECT priority FROM tasks WHERE task_id = ?", ("shared_task",))
                        current = cursor.fetchone()[0]
                        
                        # Simulate some processing
                        time.sleep(0.001)
                        
                        # Update priority
                        cursor.execute("""
                            UPDATE tasks SET priority = ? WHERE task_id = ?
                        """, (current + 1, "shared_task"))
                        
                        conn.commit()
                        
                    duration_ms = (time.time() - start_time) * 1000
                    return TransactionResult(success=True, duration_ms=duration_ms, retry_count=retry_count)
                    
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e):
                        retry_count += 1
                        time.sleep(0.01 * retry_count)  # Exponential backoff
                        continue
                    raise
            
            duration_ms = (time.time() - start_time) * 1000
            return TransactionResult(success=False, error="Max retries exceeded", 
                                   duration_ms=duration_ms, retry_count=retry_count)
        
        # Run concurrent updates
        num_threads = 10
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(increment_priority, i) for i in range(num_threads)]
            results = [f.result() for f in as_completed(futures)]
        
        # All should eventually succeed
        successes = [r for r in results if r.success]
        assert len(successes) == num_threads
        
        # Final priority should equal number of updates
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT priority FROM tasks WHERE task_id = ?", ("shared_task",))
            final_priority = cursor.fetchone()[0]
            assert final_priority == num_threads

    def test_reader_writer_conflict(self, temp_db_path: str):
        """Test readers don't block each other but writers do."""
        initialize_database(temp_db_path)
        
        # Insert test data
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            for i in range(10):
                cursor.execute("""
                    INSERT INTO tasks (task_id, channel_id, description, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (f"task_{i}", "test_channel", f"task {i}", TaskStatus.PENDING.value, datetime.now(timezone.utc), datetime.now(timezone.utc)))
            conn.commit()
        
        results: List[Tuple[str, float]] = []
        lock = threading.Lock()
        
        def reader_thread(thread_id: int):
            start = time.time()
            with get_db_connection(temp_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM tasks")
                count = cursor.fetchone()[0]
                time.sleep(0.1)  # Simulate work
            
            duration = time.time() - start
            with lock:
                results.append((f"reader_{thread_id}", duration))
        
        def writer_thread(thread_id: int):
            start = time.time()
            with get_db_connection(temp_db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO tasks (task_id, channel_id, description, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (f"new_task_{thread_id}", "test_channel", "writer task", 
                      TaskStatus.PENDING.value, datetime.now(timezone.utc), datetime.now(timezone.utc)))
                time.sleep(0.1)  # Simulate work
                conn.commit()
            
            duration = time.time() - start
            with lock:
                results.append((f"writer_{thread_id}", duration))
        
        # Start multiple readers and one writer
        threads = []
        
        # Start readers
        for i in range(3):
            t = threading.Thread(target=reader_thread, args=(i,))
            threads.append(t)
            t.start()
        
        # Give readers a head start
        time.sleep(0.05)
        
        # Start writer
        t = threading.Thread(target=writer_thread, args=(0,))
        threads.append(t)
        t.start()
        
        # Wait for all to complete
        for t in threads:
            t.join()
        
        # Analyze results
        reader_times = [d for n, d in results if n.startswith("reader_")]
        writer_times = [d for n, d in results if n.startswith("writer_")]
        
        # Readers should run concurrently (similar times)
        assert max(reader_times) - min(reader_times) < 0.05
        
        # Writer might be blocked by readers
        assert len(writer_times) == 1


class TestDeadlockHandling:
    """Test deadlock detection and recovery."""

    @pytest.fixture
    def temp_db_path(self) -> str:
        """Create a temporary database file."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)

    def test_potential_deadlock_scenario(self, temp_db_path: str):
        """Test handling of potential deadlock situations."""
        initialize_database(temp_db_path)
        
        # Insert two tasks
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tasks (task_id, channel_id, description, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("task_A", "test_channel", "Task A", TaskStatus.PENDING.value, datetime.now(timezone.utc), datetime.now(timezone.utc)))
            cursor.execute("""
                INSERT INTO tasks (task_id, channel_id, description, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("task_B", "test_channel", "Task B", TaskStatus.PENDING.value, datetime.now(timezone.utc), datetime.now(timezone.utc)))
            conn.commit()
        
        # SQLite doesn't have true deadlocks due to its locking model,
        # but we can simulate lock contention
        
        lock_acquired = threading.Event()
        deadlock_detected = threading.Event()
        
        def transaction1():
            try:
                conn = get_db_connection(temp_db_path)
                conn.execute("BEGIN IMMEDIATE")
                cursor = conn.cursor()
                
                # Update task A
                cursor.execute("UPDATE tasks SET status = ? WHERE task_id = ?",
                             (TaskStatus.ACTIVE.value, "task_A"))
                
                # Signal that we have the lock
                lock_acquired.set()
                
                # Wait a bit
                time.sleep(0.1)
                
                # Try to update task B (might be locked by transaction2)
                cursor.execute("UPDATE tasks SET status = ? WHERE task_id = ?",
                             (TaskStatus.ACTIVE.value, "task_B"))
                
                conn.commit()
                conn.close()
                
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    deadlock_detected.set()
                conn.rollback()
                conn.close()
        
        def transaction2():
            # Wait for transaction1 to acquire lock
            lock_acquired.wait()
            
            try:
                conn = get_db_connection(temp_db_path)
                conn.execute("BEGIN IMMEDIATE")
                cursor = conn.cursor()
                
                # This will wait because transaction1 has the lock
                cursor.execute("UPDATE tasks SET status = ? WHERE task_id = ?",
                             (TaskStatus.COMPLETED.value, "task_B"))
                
                conn.commit()
                conn.close()
                
            except sqlite3.OperationalError:
                conn.rollback()
                conn.close()
        
        # Run both transactions
        t1 = threading.Thread(target=transaction1)
        t2 = threading.Thread(target=transaction2)
        
        t1.start()
        t2.start()
        
        t1.join(timeout=2.0)
        t2.join(timeout=2.0)
        
        # In SQLite, one transaction will wait for the other
        # No true deadlock occurs due to single-writer model


class TestLongRunningTransactions:
    """Test handling of long-running transactions."""

    @pytest.fixture
    def temp_db_path(self) -> str:
        """Create a temporary database file."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)

    def test_transaction_timeout(self, temp_db_path: str):
        """Test transaction timeout handling."""
        initialize_database(temp_db_path)
        
        # Set a short busy timeout
        with get_db_connection(temp_db_path) as conn:
            conn.execute("PRAGMA busy_timeout = 100")  # 100ms timeout
        
        # Start a long-running transaction
        long_conn = get_db_connection(temp_db_path)
        long_conn.execute("BEGIN EXCLUSIVE")
        
        # Try to access from another connection
        start_time = time.time()
        try:
            with get_db_connection(temp_db_path) as conn:
                conn.execute("PRAGMA busy_timeout = 100")
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM tasks")
                
        except sqlite3.OperationalError as e:
            elapsed = time.time() - start_time
            assert "database is locked" in str(e)
            assert elapsed < 0.2  # Should timeout quickly
        
        finally:
            long_conn.rollback()
            long_conn.close()

    def test_wal_mode_concurrent_reads(self, temp_db_path: str):
        """Test WAL mode allows concurrent reads during write."""
        initialize_database(temp_db_path)
        
        # Enable WAL mode
        with get_db_connection(temp_db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.commit()
        
        # Insert test data
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            for i in range(100):
                cursor.execute("""
                    INSERT INTO tasks (task_id, channel_id, description, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (f"task_{i}", "test_channel", f"task {i}", TaskStatus.PENDING.value, datetime.now(timezone.utc), datetime.now(timezone.utc)))
            conn.commit()
        
        # Start a write transaction
        write_conn = get_db_connection(temp_db_path)
        write_conn.execute("PRAGMA journal_mode=WAL")
        write_conn.execute("BEGIN")
        write_cursor = write_conn.cursor()
        
        # Start updating
        for i in range(50):
            write_cursor.execute("""
                UPDATE tasks SET status = ? WHERE task_id = ?
            """, (TaskStatus.ACTIVE.value, f"task_{i}"))
        
        # While write is in progress, reads should still work
        read_results = []
        
        def read_task(task_id: str):
            with get_db_connection(temp_db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("SELECT status FROM tasks WHERE task_id = ?", (task_id,))
                result = cursor.fetchone()
                read_results.append((task_id, result[0]))
        
        # Read from multiple threads
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(read_task, f"task_{i}") for i in range(60, 70)]
            for f in as_completed(futures):
                f.result()
        
        # Reads should see old values (PENDING) since write hasn't committed
        for task_id, status in read_results:
            assert status == TaskStatus.PENDING.value
        
        # Commit the write
        write_conn.commit()
        write_conn.close()
        
        # Now reads should see new values
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM tasks WHERE task_id = ?", ("task_0",))
            assert cursor.fetchone()[0] == TaskStatus.ACTIVE.value