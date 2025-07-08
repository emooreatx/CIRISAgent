"""Unit tests for CIRISRuntime."""

import pytest
import asyncio
import tempfile
import os

# CRITICAL: Import and use the proper function to allow runtime creation
from ciris_engine.logic.runtime.prevent_sideeffects import allow_runtime_creation
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from pathlib import Path

from ciris_engine.logic.runtime.ciris_runtime import CIRISRuntime
from ciris_engine.schemas.config.essential import EssentialConfig
# CognitiveState removed - using AgentState instead

# Note: These tests may have ordering issues when run as part of the full test suite
# but pass when run individually


class TestCIRISRuntime:
    """Test cases for CIRISRuntime."""

    @pytest.fixture(autouse=True)
    def allow_runtime(self):
        """Allow runtime creation for these tests."""
        allow_runtime_creation()
        try:
            yield
        finally:
            # Restore original state
            if os.environ.get('CIRIS_IMPORT_MODE') is None:
                os.environ['CIRIS_IMPORT_MODE'] = 'true'

    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
