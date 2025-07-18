# CRITICAL: Prevent side effects during imports
import os
os.environ['CIRIS_IMPORT_MODE'] = 'true'
os.environ['CIRIS_MOCK_LLM'] = 'true'

import pytest
from unittest.mock import AsyncMock, MagicMock, ANY
from click.testing import CliRunner
from typing import List

import main
from ciris_engine.logic.runtime.ciris_runtime import CIRISRuntime


def test_run_discord_uses_env(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "abc")
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "111")
    monkeypatch.setenv("DISCORD_DEFERRAL_CHANNEL_ID", "222")

    # Mock CIRISRuntime
    runtime_mock = MagicMock(spec=CIRISRuntime)
    runtime_mock.initialize = AsyncMock()
    runtime_mock.shutdown = AsyncMock()
    runtime_mock.startup_channel_id = "111"
    runtime_mock._shutdown_complete = True  # Mark as shutdown complete to prevent monitor task from forcing exit

    monkeypatch.setattr("ciris_engine.logic.runtime.ciris_runtime.CIRISRuntime.__new__", lambda cls, *args, **kwargs: runtime_mock)
    monkeypatch.setattr("ciris_engine.logic.runtime.ciris_runtime.CIRISRuntime.__init__", lambda self, *args, **kwargs: None)

    monkeypatch.setattr(main, "load_config", AsyncMock(return_value=MagicMock(discord_home_channel_id="111")))
    monkeypatch.setattr(main, "_run_runtime", AsyncMock())

    # Mock os._exit to prevent actual exit
    def mock_exit(code):
        pass  # Don't actually exit
    
    monkeypatch.setattr("os._exit", mock_exit)

    import asyncio as real_asyncio

    real_run = real_asyncio.run

    def fake_run(coro):
        real_run(coro)

    monkeypatch.setattr("asyncio.run", fake_run)

    result = CliRunner().invoke(main.main, [])
    assert result.exit_code == 0
    runtime_mock.initialize.assert_called_once()


