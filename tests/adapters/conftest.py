"""
Shared fixtures for adapter tests.

This conftest.py provides database initialization for all adapter tests
to prevent sqlite3.OperationalError: no such table errors.
"""
import os
import sys
import pytest
import tempfile
from ciris_engine.logic.persistence import initialize_database
from ciris_engine.logic import persistence


@pytest.fixture
def test_db():
    """Create a temporary test database for each test."""
    # Create a temporary database file
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # Ensure the database file is writable
    os.chmod(db_path, 0o666)
    
    # Initialize the database
    initialize_database(db_path)
    
    # Set the persistence module to use our test database
    original_db_path = persistence._db_path if hasattr(persistence, '_db_path') else None
    persistence._db_path = db_path
    
    # Re-initialize persistence with test database
    if hasattr(persistence, '_init_db'):
        persistence._init_db()
    
    yield db_path
    
    # Cleanup
    try:
        os.unlink(db_path)
    except:
        pass
    
    # Restore original database path
    if original_db_path:
        persistence._db_path = original_db_path
        if hasattr(persistence, '_init_db'):
            persistence._init_db()


@pytest.fixture(autouse=True)
def auto_test_db(test_db):
    """
    Automatically use test database for all adapter tests.
    
    This fixture is automatically used for every test in the adapters directory
    to ensure that database operations don't fail with missing tables.
    """
    # The test_db fixture already handles initialization and cleanup
    return test_db