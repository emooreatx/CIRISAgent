import pytest
from unittest.mock import AsyncMock, MagicMock, ANY
from click.testing import CliRunner
import main
from ciris_engine.runtime.discord_runtime import DiscordRuntime


def test_run_discord_uses_env(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "abc")
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "111")
    monkeypatch.setenv("DISCORD_DEFERRAL_CHANNEL_ID", "222")
    mock_runtime = MagicMock()
    monkeypatch.setattr(main, "create_runtime", MagicMock(return_value=mock_runtime))
    monkeypatch.setattr(main, "load_config", AsyncMock(return_value=MagicMock(discord_channel_id="111")))
    monkeypatch.setattr(main, "_run_runtime", AsyncMock())
    monkeypatch.setattr(mock_runtime, "initialize", AsyncMock())
    monkeypatch.setattr(mock_runtime, "shutdown", AsyncMock())

    import asyncio as real_asyncio
    import types

    real_run = real_asyncio.run

    def fake_run(coro):
        real_run(coro)

    monkeypatch.setattr(main, "asyncio", types.SimpleNamespace(run=fake_run))

    result = CliRunner().invoke(main.main, [])
    assert result.exit_code == 0
    main.create_runtime.assert_called_once()
    args = main.create_runtime.call_args[0]
    assert args[0] == "discord"
    assert args[1] == "default"
    assert args[2] == ANY


@pytest.mark.asyncio
async def test_discord_runtime_cli_fallback(monkeypatch):
    monkeypatch.setattr(
        "ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.start",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.get_client",
        MagicMock(return_value=MagicMock(model_name="test", instruct_client=None, client=None)),
    )
    monkeypatch.setattr(
        "ciris_engine.runtime.ciris_runtime.CIRISRuntime._build_components",
        AsyncMock(),
    )
    # Observers have been removed; no start methods to patch
    monkeypatch.setattr(
        "ciris_engine.runtime.discord_runtime.CLIAdapter.start", AsyncMock()
    )
    monkeypatch.setattr(
        "ciris_engine.sinks.multi_service_sink.MultiServiceActionSink.start", AsyncMock()
    )

    runtime = DiscordRuntime(token="tok", profile_name="p", startup_channel_id="chan")
    await runtime.initialize()
    info = runtime.service_registry.get_provider_info()
    comm = info["handlers"]["SpeakHandler"]["communication"]
    assert any(
        p["priority"] == "HIGH" and p["name"].startswith("DiscordAdapter") for p in comm
    )
    assert any(
        p["priority"] == "NORMAL" and p["name"].startswith("CLIAdapter") for p in comm
    )
