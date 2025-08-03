"""Configuration for the test tool."""

from pathlib import Path

# Output directory for test logs
TEST_OUTPUT_DIR = Path.home() / ".ciris_test_runs"

# Docker container name
CONTAINER_NAME = "ciris-pytest"

# Status file for tracking current run
STATUS_FILE = TEST_OUTPUT_DIR / "current_run.json"

# Default compose file
DEFAULT_COMPOSE_FILE = "docker/docker-compose-pytest.yml"

# Test timeout in seconds
DEFAULT_TIMEOUT = 60

# Coverage thresholds
COVERAGE_WARNING_THRESHOLD = 80
COVERAGE_ERROR_THRESHOLD = 60