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

from .runner import TestRunner
from .config import TEST_OUTPUT_DIR, CONTAINER_NAME

__all__ = ['TestRunner', 'TEST_OUTPUT_DIR', 'CONTAINER_NAME']