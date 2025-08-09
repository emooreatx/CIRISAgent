"""
Tests for ModuleLoader with MOCK safety checks.
"""

import json
import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from ciris_engine.logic.runtime.module_loader import ModuleLoader
from ciris_engine.schemas.runtime.enums import ServiceType
from ciris_engine.schemas.runtime.manifest import ServiceManifest, ServiceMetadata


@pytest.fixture
def temp_modules_dir():
    """Create a temporary directory for test modules."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_manifest():
    """Create a mock module manifest."""
    return {
        "module": {
            "name": "mock_llm",
            "version": "1.0.0",
            "description": "Mock LLM for testing",
            "author": "CIRIS Test Suite",
            "is_mock": True,
        },
        "services": [
            {
                "type": "LLM",
                "class": "mock_llm.service.MockLLMService",
                "capabilities": ["llm_generation", "text_completion"],
            }
        ],
        "capabilities": ["llm_generation", "text_completion"],
    }


@pytest.fixture
def real_manifest():
    """Create a real module manifest."""
    return {
        "module": {
            "name": "real_llm",
            "version": "1.0.0",
            "description": "Real LLM service",
            "author": "CIRIS Test Suite",
            "is_mock": False,
        },
        "services": [
            {
                "type": "LLM",
                "class": "real_llm.service.RealLLMService",
                "capabilities": ["llm_generation", "text_completion"],
            }
        ],
        "capabilities": ["llm_generation", "text_completion"],
    }


def create_module(modules_dir: Path, module_name: str, manifest_data: dict):
    """Helper to create a module with manifest."""
    module_path = modules_dir / module_name
    module_path.mkdir(parents=True, exist_ok=True)

    manifest_path = module_path / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f)

    return module_path


class TestModuleLoader:
    """Test suite for ModuleLoader."""

    def test_initialization(self, temp_modules_dir):
        """Test ModuleLoader initialization."""
        loader = ModuleLoader(modules_dir=temp_modules_dir)

        assert loader.modules_dir == temp_modules_dir
        assert loader.loaded_modules == {}
        assert loader.mock_modules == set()
        assert loader.disabled_service_types == set()

    def test_initialization_default_dir(self):
        """Test ModuleLoader with default directory."""
        loader = ModuleLoader()

        assert loader.modules_dir == Path("ciris_modular_services")
        assert loader.loaded_modules == {}

    def test_load_module_not_found(self, temp_modules_dir, caplog):
        """Test loading a non-existent module."""
        loader = ModuleLoader(modules_dir=temp_modules_dir)

        with caplog.at_level(logging.ERROR):
            result = loader.load_module("nonexistent")

        assert result is False
        assert "Module nonexistent not found" in caplog.text

    def test_load_mock_module(self, temp_modules_dir, mock_manifest, caplog):
        """Test loading a mock module with warnings."""
        create_module(temp_modules_dir, "mock_llm", mock_manifest)
        loader = ModuleLoader(modules_dir=temp_modules_dir)

        with caplog.at_level(logging.WARNING):
            result = loader.load_module("mock_llm")

        assert result is True
        assert "mock_llm" in loader.loaded_modules
        assert "mock_llm" in loader.mock_modules
        assert ServiceType.LLM in loader.disabled_service_types

        # Check for loud warnings
        assert "MOCK MODULE DETECTED" in caplog.text
        assert "THIS IS FOR TESTING ONLY" in caplog.text

    def test_load_mock_module_with_disable_core(self, temp_modules_dir, mock_manifest, caplog):
        """Test loading mock module with core service disabling."""
        create_module(temp_modules_dir, "mock_llm", mock_manifest)
        loader = ModuleLoader(modules_dir=temp_modules_dir)

        with caplog.at_level(logging.WARNING):
            result = loader.load_module("mock_llm", disable_core=True)

        assert result is True
        assert "DISABLING all non-mock LLM services" in caplog.text
        assert "ONLY mock_llm will provide LLM services" in caplog.text

    def test_load_real_module(self, temp_modules_dir, real_manifest, caplog):
        """Test loading a real module."""
        create_module(temp_modules_dir, "real_llm", real_manifest)
        loader = ModuleLoader(modules_dir=temp_modules_dir)

        with caplog.at_level(logging.INFO):
            result = loader.load_module("real_llm")

        assert result is True
        assert "real_llm" in loader.loaded_modules
        assert "real_llm" not in loader.mock_modules
        assert ServiceType.LLM not in loader.disabled_service_types
        assert "Loading module: real_llm" in caplog.text

    def test_mock_safety_violation(self, temp_modules_dir, mock_manifest, real_manifest):
        """Test that loading real module after mock is prevented."""
        # First load mock module
        create_module(temp_modules_dir, "mock_llm", mock_manifest)
        create_module(temp_modules_dir, "real_llm", real_manifest)

        loader = ModuleLoader(modules_dir=temp_modules_dir)
        loader.load_module("mock_llm")

        # Now try to load real module - should fail
        with pytest.raises(RuntimeError, match="MOCK safety violation"):
            loader._handle_real_module("real_llm", ServiceManifest.model_validate(real_manifest))

    def test_invalid_manifest(self, temp_modules_dir):
        """Test loading module with invalid manifest."""
        invalid_manifest = {
            "module": {
                # Missing required fields
                "name": "invalid"
            }
        }
        create_module(temp_modules_dir, "invalid", invalid_manifest)

        loader = ModuleLoader(modules_dir=temp_modules_dir)
        result = loader.load_module("invalid")

        assert result is False

    def test_manifest_validation_errors(self, temp_modules_dir, caplog):
        """Test module with manifest validation errors."""
        # Create a manifest that will fail validation
        bad_manifest = {
            "module": {
                "name": "bad_module",
                "version": "1.0.0",
                "is_mock": False,
                "description": "Module with validation issues",
            },
            "services": [],  # Empty services might cause validation error
        }
        create_module(temp_modules_dir, "bad_module", bad_manifest)

        loader = ModuleLoader(modules_dir=temp_modules_dir)

        # Mock the validate_manifest method to return errors
        with patch.object(ServiceManifest, "validate_manifest", return_value=["Error 1", "Error 2"]):
            with caplog.at_level(logging.ERROR):
                result = loader.load_module("bad_module")

            assert result is False
            assert "Manifest validation errors" in caplog.text

    def test_is_service_type_mocked(self, temp_modules_dir, mock_manifest):
        """Test checking if a service type is mocked."""
        create_module(temp_modules_dir, "mock_llm", mock_manifest)
        loader = ModuleLoader(modules_dir=temp_modules_dir)

        # Before loading mock
        assert loader.is_service_type_mocked(ServiceType.LLM) is False

        # After loading mock
        loader.load_module("mock_llm")
        assert loader.is_service_type_mocked(ServiceType.LLM) is True
        assert loader.is_service_type_mocked(ServiceType.MEMORY) is False

    def test_get_mock_warnings(self, temp_modules_dir, mock_manifest):
        """Test getting mock warnings."""
        create_module(temp_modules_dir, "mock_llm", mock_manifest)
        loader = ModuleLoader(modules_dir=temp_modules_dir)

        # Initially no warnings
        warnings = loader.get_mock_warnings()
        assert warnings == []

        # After loading mock module
        loader.load_module("mock_llm")
        warnings = loader.get_mock_warnings()

        assert len(warnings) > 0
        assert any("MOCK MODULES ACTIVE" in w for w in warnings)
        assert any("mock_llm" in w for w in warnings)

    def test_multiple_mock_modules(self, temp_modules_dir):
        """Test loading multiple mock modules."""
        mock_llm = {
            "module": {
                "name": "mock_llm",
                "version": "1.0.0",
                "description": "Mock LLM",
                "author": "Test",
                "is_mock": True,
            },
            "services": [{"type": "LLM", "class": "mock_llm.MockLLM", "capabilities": ["llm"]}],
        }
        mock_memory = {
            "module": {
                "name": "mock_memory",
                "version": "1.0.0",
                "description": "Mock Memory",
                "author": "Test",
                "is_mock": True,
            },
            "services": [{"type": "MEMORY", "class": "mock_memory.MockMemory", "capabilities": ["memory"]}],
        }

        create_module(temp_modules_dir, "mock_llm", mock_llm)
        create_module(temp_modules_dir, "mock_memory", mock_memory)

        loader = ModuleLoader(modules_dir=temp_modules_dir)

        assert loader.load_module("mock_llm") is True
        assert loader.load_module("mock_memory") is True

        assert "mock_llm" in loader.mock_modules
        assert "mock_memory" in loader.mock_modules
        assert ServiceType.LLM in loader.disabled_service_types
        assert ServiceType.MEMORY in loader.disabled_service_types

    def test_load_module_exception_handling(self, temp_modules_dir, caplog):
        """Test exception handling during module load."""
        # Create a module with malformed JSON
        module_path = temp_modules_dir / "broken"
        module_path.mkdir()
        manifest_path = module_path / "manifest.json"

        with open(manifest_path, "w") as f:
            f.write("{ invalid json }")

        loader = ModuleLoader(modules_dir=temp_modules_dir)

        with caplog.at_level(logging.ERROR):
            result = loader.load_module("broken")

        assert result is False
        assert "Failed to load module broken" in caplog.text

    def test_critical_logging_for_mock(self, temp_modules_dir, mock_manifest, caplog):
        """Test that loading mock modules logs at CRITICAL level."""
        create_module(temp_modules_dir, "mock_llm", mock_manifest)
        loader = ModuleLoader(modules_dir=temp_modules_dir)

        with caplog.at_level(logging.CRITICAL):
            loader.load_module("mock_llm")

        # Check for critical log about mock module
        critical_logs = [r for r in caplog.records if r.levelno == logging.CRITICAL]
        assert len(critical_logs) > 0
        assert "MOCK_MODULE_LOADED" in critical_logs[0].message
        assert "mock_llm" in critical_logs[0].message
