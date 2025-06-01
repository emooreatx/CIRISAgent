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
