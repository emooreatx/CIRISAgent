import types
import asyncio
from click.testing import CliRunner
from unittest.mock import AsyncMock, MagicMock

import main


def test_cli_offline_non_interactive(monkeypatch):
    """Ensure CLI mode works with the mock LLM service."""
    monkeypatch.setattr(main, "load_config", AsyncMock(return_value=MagicMock(discord_channel_id="cli")))

    runtime = MagicMock()
    monkeypatch.setattr(main, "create_runtime", MagicMock(return_value=runtime))
    monkeypatch.setattr(main, "_run_runtime", AsyncMock())
    monkeypatch.setattr(runtime, "initialize", AsyncMock())
    monkeypatch.setattr(runtime, "shutdown", AsyncMock())

    real_run = asyncio.run

    def fake_run(coro):
        real_run(coro)

    monkeypatch.setattr(main, "asyncio", types.SimpleNamespace(run=fake_run))

    result = CliRunner().invoke(main.main, ["--mode", "cli", "--no-interactive", "--mock-llm"])
    assert result.exit_code == 0
    main.create_runtime.assert_called_once()
