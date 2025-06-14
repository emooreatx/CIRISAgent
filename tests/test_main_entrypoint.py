import pytest
from unittest.mock import AsyncMock, MagicMock

import main as main_module
from ciris_engine.runtime.ciris_runtime import CIRISRuntime


def test_main_function_existence():
    """Test that the main function exists and is callable."""
    assert hasattr(main_module, 'main')
    assert callable(main_module.main)
    
def test_helper_functions_exist():
    """Test that helper functions exist."""
    assert hasattr(main_module, '_create_thought')
    assert callable(main_module._create_thought)
    assert hasattr(main_module, '_run_runtime')
    assert callable(main_module._run_runtime)


def test_ciris_runtime_initialization(monkeypatch):
    """Test that CIRISRuntime can be initialized with different modes."""
    mock_runtime = MagicMock()
    monkeypatch.setattr("ciris_engine.runtime.ciris_runtime.CIRISRuntime", MagicMock(return_value=mock_runtime))
    
    from ciris_engine.runtime.ciris_runtime import CIRISRuntime
    
    # Test Discord mode
    CIRISRuntime(modes=["discord"], profile_name="test")
    
    # Test CLI mode 
    CIRISRuntime(modes=["cli"], profile_name="test")
    
    # Test API mode
    CIRISRuntime(modes=["api"], profile_name="test")
    
    # Verify CIRISRuntime was called 3 times
    assert CIRISRuntime.call_count == 3  # type: ignore[attr-defined]


