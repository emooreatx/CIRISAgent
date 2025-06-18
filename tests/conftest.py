"""
Global test configuration for pytest.

This file is automatically loaded by pytest and contains setup that applies to all tests.
"""
import os
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

import pytest
import asyncio
import gc

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
    import time
    time.sleep(0.1)
