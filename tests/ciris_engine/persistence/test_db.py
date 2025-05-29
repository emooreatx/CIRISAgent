import pytest
import sqlite3
from unittest.mock import patch
from ciris_engine.persistence import db
import tempfile
import os

def in_memory_db_path():
    return ":memory:"

def temp_db_file():
    f = tempfile.NamedTemporaryFile(delete=False)
    f.close()
    return f.name

@patch("ciris_engine.persistence.db.get_sqlite_db_full_path", new=in_memory_db_path)
def test_initialize_database_and_get_all_tasks():
    db_path = temp_db_file()
    try:
        db.initialize_database(db_path=db_path)
        assert db.get_all_tasks(db_path=db_path) == []
    finally:
        os.unlink(db_path)

@patch("ciris_engine.persistence.db.get_sqlite_db_full_path", new=in_memory_db_path)
def test_insert_and_get_tasks_by_status():
    db_path = temp_db_file()
    try:
        db.initialize_database(db_path=db_path)
        with db.get_db_connection(db_path) as conn:
            conn.execute("INSERT INTO tasks (task_id, description, status, priority, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                         ("t1", "desc1", "active", 1, "2025-05-28T00:00:00Z", "2025-05-28T00:00:00Z"))
            conn.execute("INSERT INTO tasks (task_id, description, status, priority, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                         ("t2", "desc2", "completed", 2, "2025-05-27T00:00:00Z", "2025-05-27T00:00:00Z"))
            conn.commit()
        all_tasks = db.get_all_tasks(db_path=db_path)
        assert len(all_tasks) == 2
        active_tasks = db.get_tasks_by_status("active", db_path=db_path)
        assert len(active_tasks) == 1
        assert active_tasks[0]["task_id"] == "t1"
        completed_tasks = db.get_tasks_by_status("completed", db_path=db_path)
        assert len(completed_tasks) == 1
        assert completed_tasks[0]["task_id"] == "t2"
    finally:
        os.unlink(db_path)

@patch("ciris_engine.persistence.db.get_sqlite_db_full_path", new=in_memory_db_path)
def test_insert_and_get_thoughts_by_status():
    db_path = temp_db_file()
    try:
        db.initialize_database(db_path=db_path)
        with db.get_db_connection(db_path) as conn:
            conn.execute("INSERT INTO tasks (task_id, description, status, priority, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                         ("t1", "desc1", "active", 1, "2025-05-28T00:00:00Z", "2025-05-28T00:00:00Z"))
            conn.execute("INSERT INTO thoughts (thought_id, source_task_id, status, created_at, updated_at, content) VALUES (?, ?, ?, ?, ?, ?)",
                         ("th1", "t1", "pending", "2025-05-28T00:00:00Z", "2025-05-28T00:00:00Z", "content1"))
            conn.execute("INSERT INTO thoughts (thought_id, source_task_id, status, created_at, updated_at, content) VALUES (?, ?, ?, ?, ?, ?)",
                         ("th2", "t1", "processing", "2025-05-28T00:00:00Z", "2025-05-28T00:00:00Z", "content2"))
            conn.commit()
        pending = db.get_thoughts_by_status("pending", db_path=db_path)
        assert len(pending) == 1
        assert pending[0]["thought_id"] == "th1"
        processing = db.get_thoughts_by_status("processing", db_path=db_path)
        assert len(processing) == 1
        assert processing[0]["thought_id"] == "th2"
    finally:
        os.unlink(db_path)

@patch("ciris_engine.persistence.db.get_sqlite_db_full_path", new=in_memory_db_path)
def test_get_tasks_older_than():
    db_path = temp_db_file()
    try:
        db.initialize_database(db_path=db_path)
        with db.get_db_connection(db_path) as conn:
            conn.execute("INSERT INTO tasks (task_id, description, status, priority, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                         ("t1", "desc1", "active", 1, "2025-05-27T00:00:00Z", "2025-05-27T00:00:00Z"))
            conn.execute("INSERT INTO tasks (task_id, description, status, priority, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                         ("t2", "desc2", "active", 2, "2025-05-28T00:00:00Z", "2025-05-28T00:00:00Z"))
            conn.commit()
        older = db.get_tasks_older_than("2025-05-28T00:00:00Z", db_path=db_path)
        assert len(older) == 1
        assert older[0]["task_id"] == "t1"
    finally:
        os.unlink(db_path)

@patch("ciris_engine.persistence.db.get_sqlite_db_full_path", new=in_memory_db_path)
def test_get_thoughts_older_than():
    db_path = temp_db_file()
    try:
        db.initialize_database(db_path=db_path)
        with db.get_db_connection(db_path) as conn:
            conn.execute("INSERT INTO tasks (task_id, description, status, priority, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                         ("t1", "desc1", "active", 1, "2025-05-28T00:00:00Z", "2025-05-28T00:00:00Z"))
            conn.execute("INSERT INTO thoughts (thought_id, source_task_id, status, created_at, updated_at, content) VALUES (?, ?, ?, ?, ?, ?)",
                         ("th1", "t1", "pending", "2025-05-27T00:00:00Z", "2025-05-27T00:00:00Z", "content1"))
            conn.execute("INSERT INTO thoughts (thought_id, source_task_id, status, created_at, updated_at, content) VALUES (?, ?, ?, ?, ?, ?)",
                         ("th2", "t1", "pending", "2025-05-28T00:00:00Z", "2025-05-28T00:00:00Z", "content2"))
            conn.commit()
        older = db.get_thoughts_older_than("2025-05-28T00:00:00Z", db_path=db_path)
        assert len(older) == 1
        assert older[0]["thought_id"] == "th1"
    finally:
        os.unlink(db_path)
