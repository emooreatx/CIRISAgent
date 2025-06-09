import types
import asyncio
from click.testing import CliRunner
from unittest.mock import AsyncMock, MagicMock
from typing import List

import main
from ciris_engine.runtime.ciris_runtime import CIRISRuntime


def test_cli_offline_non_interactive(monkeypatch):
    """Ensure CLI mode works with the mock LLM service."""
    monkeypatch.setattr(main, "load_config", AsyncMock(return_value=MagicMock(discord_channel_id="cli")))

    # Mock CIRISRuntime constructor and methods
    runtime_mock = MagicMock(spec=CIRISRuntime)
    runtime_mock.initialize = AsyncMock()
    runtime_mock.shutdown = AsyncMock()
    runtime_mock.startup_channel_id = "cli"
    
    def mock_runtime_init(modes: List[str], **kwargs):
        return runtime_mock
    
    monkeypatch.setattr("ciris_engine.runtime.ciris_runtime.CIRISRuntime.__new__", lambda cls, *args, **kwargs: runtime_mock)
    monkeypatch.setattr("ciris_engine.runtime.ciris_runtime.CIRISRuntime.__init__", lambda self, *args, **kwargs: None)
    
    monkeypatch.setattr(main, "_run_runtime", AsyncMock())

    real_run = asyncio.run

    def fake_run(coro):
        real_run(coro)

    monkeypatch.setattr(main, "asyncio", types.SimpleNamespace(run=fake_run))

    result = CliRunner().invoke(main.main, ["--mode", "cli", "--no-interactive", "--mock-llm"])
    assert result.exit_code == 0
    runtime_mock.initialize.assert_called_once()