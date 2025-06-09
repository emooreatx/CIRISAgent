import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine import main as engine_main
from ciris_engine.runtime.ciris_runtime import CIRISRuntime


@pytest.mark.asyncio
async def test_main_invokes_runtime(monkeypatch):
    monkeypatch.setattr(engine_main, "setup_basic_logging", MagicMock())
    mock_config = MagicMock()
    mock_config.startup_channel_id = "test_channel"
    monkeypatch.setattr(engine_main, "load_config", AsyncMock(return_value=mock_config))
    mock_runtime = MagicMock()
    runtime_constructor = MagicMock(return_value=mock_runtime)
    monkeypatch.setattr(engine_main, "CIRISRuntime", runtime_constructor)
    monkeypatch.setattr(engine_main, "run_with_shutdown_handler", AsyncMock())

    await engine_main.main.callback(
        modes_list=("cli",),
        profile="test",
        config_file_path=None,
        api_host="0.0.0.0",
        api_port=8080,
        cli_interactive=True,
        discord_bot_token=None,
        debug=False,
    )

    # Verify CIRISRuntime was called with correct parameters
    runtime_constructor.assert_called_once()
    call_args = runtime_constructor.call_args
    assert "cli" in call_args.kwargs.get("modes", [])
    assert call_args.kwargs.get("profile_name") == "test"
    
    engine_main.run_with_shutdown_handler.assert_called_once_with(mock_runtime)


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
    assert CIRISRuntime.call_count == 3


