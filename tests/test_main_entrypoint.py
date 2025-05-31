import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine import main as engine_main


@pytest.mark.asyncio
async def test_main_invokes_runtime(monkeypatch):
    monkeypatch.setattr(engine_main, "setup_basic_logging", MagicMock())
    mock_config = MagicMock(discord_channel_id="123")
    monkeypatch.setattr(engine_main, "load_config", AsyncMock(return_value=mock_config))
    runtime = MagicMock()
    monkeypatch.setattr(engine_main, "create_runtime", MagicMock(return_value=runtime))
    monkeypatch.setattr(engine_main, "run_with_shutdown_handler", AsyncMock())

    await engine_main.main.callback(
        mode="cli",
        profile="test",
        config=None,
        host="0.0.0.0",
        port=8080,
        no_interactive=False,
        debug=False,
    )

    engine_main.create_runtime.assert_called_once_with(
        "cli",
        "test",
        mock_config,
        interactive=True,
        host="0.0.0.0",
        port=8080,
    )
    engine_main.run_with_shutdown_handler.assert_called_once_with(runtime)


def test_create_runtime_dispatch(monkeypatch):
    config = MagicMock(discord_channel_id="chan")
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    monkeypatch.setattr(engine_main, "DiscordRuntime", MagicMock())
    monkeypatch.setattr(engine_main, "CLIRuntime", MagicMock())
    monkeypatch.setattr(engine_main, "APIRuntime", MagicMock())

    engine_main.create_runtime("discord", "p", config)
    engine_main.DiscordRuntime.assert_called_once()

    engine_main.create_runtime("cli", "p", config)
    engine_main.CLIRuntime.assert_called_once()

    engine_main.create_runtime("api", "p", config)
    engine_main.APIRuntime.assert_called_once()


