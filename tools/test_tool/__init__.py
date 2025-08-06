"""
CIRIS Test Tool - Advanced test runner for Docker-based pytest execution.

This tool provides:
- Background test execution in Docker containers
- Automatic container rebuilding
- Test filtering and selection
- Real-time status monitoring
- Error extraction and reporting
- Coverage analysis
"""

from .config import CONTAINER_NAME, TEST_OUTPUT_DIR
from .runner import TestRunner

__all__ = ["TestRunner", "TEST_OUTPUT_DIR", "CONTAINER_NAME"]
