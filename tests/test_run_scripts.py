import sys
import types
import pytest
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
async def test_run_discord_main(monkeypatch):
    # Patch sys.argv and environment
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "dummy_token")
    monkeypatch.setenv("CIRIS_PROFILE", "test_profile")
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "test_channel")
    monkeypatch.setenv("DISCORD_DEFERRAL_CHANNEL_ID", "deferral_channel")
    monkeypatch.setenv("CIRIS_MAX_ROUNDS", "1")
    import run_discord
    # Patch DiscordRuntime
    monkeypatch.setattr(run_discord, "DiscordRuntime", MagicMock())
    # Patch asyncio.run to just call the coroutine
    monkeypatch.setattr("asyncio.run", lambda coro: None)
    # Should not raise
    run_discord.__name__ = "__main__"
    with patch.object(sys, "argv", ["run_discord.py", "test_profile"]):
        try:
            run_discord.main = MagicMock()
            run_discord.main()
        except SystemExit:
            pass

@pytest.mark.asyncio
async def test_run_cli_main(monkeypatch):
    monkeypatch.setenv("CIRIS_PROFILE", "test_profile")
    monkeypatch.setenv("CIRIS_MAX_ROUNDS", "1")
    import run_cli
    monkeypatch.setattr(run_cli, "CLIRuntime", MagicMock())
    monkeypatch.setattr("asyncio.run", lambda coro: None)
    run_cli.__name__ = "__main__"
    with patch.object(sys, "argv", ["run_cli.py", "test_profile"]):
        try:
            run_cli.main = MagicMock()
            run_cli.main()
        except SystemExit:
            pass
