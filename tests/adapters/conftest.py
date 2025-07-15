"""
Shared fixtures for adapter tests.

This conftest.py provides database initialization for all adapter tests
to prevent sqlite3.OperationalError: no such table errors.
"""
import pytest


@pytest.fixture(autouse=True)
def auto_test_db(test_db):
    """
    Automatically use test database for all adapter tests.
    
    This fixture is automatically used for every test in the adapters directory
    to ensure that database operations don't fail with missing tables.
    
    The test_db fixture is imported from the main conftest.py which imports it
    from tests/fixtures/database.py.
    """
    # The test_db fixture already handles initialization and cleanup
    return test_db