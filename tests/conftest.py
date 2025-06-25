"""
Global test configuration for pytest.

This file is automatically loaded by pytest and contains setup that applies to all tests.
"""
import os
import pytest
import asyncio
from pathlib import Path

# Load environment variables from .env file for all tests
try:
    from dotenv import load_dotenv
    # Find the .env file in the project root
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    # If python-dotenv is not installed, silently continue
    pass

# Import API fixtures to ensure port randomization
from .fixtures_api import randomize_api_port, api_port

import gc
import time

@pytest.fixture(autouse=True, scope="function")
def cleanup_after_test():
    """
    Ensure proper cleanup after each test.
    This helps prevent interference between tests, especially when Discord is involved.
    """
    yield
    
    # Force garbage collection to clean up any lingering objects
    gc.collect()
    
    # Add a small delay to allow sockets to close
    time.sleep(0.1)

# Import WA test harness fixtures (when available)
try:
    from ciris_engine.logic.services.test_wa_auth_harness import (
        wa_test_harness, wa_test_env, wa_test_keys
    )
except ImportError:
    # WA test harness not available yet
    wa_test_harness = None
    wa_test_env = None
    wa_test_keys = None

# SDK client fixture removed - ciris_sdk no longer exists


# Remove the event_loop fixture - let pytest-asyncio handle it
# The asyncio_mode = auto in pytest.ini will create event loops as needed


@pytest.fixture
def api_required():
    """Mark test as requiring running API."""
    import socket
    
    # Check if API is accessible
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 8080))
        sock.close()
        
        if result != 0:
            pytest.skip("API not running on localhost:8080")
    except Exception:
        pytest.skip("Cannot check API availability")
