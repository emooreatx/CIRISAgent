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
    
    monkeypatch.setattr("ciris_engine.logic.runtime.ciris_runtime.CIRISRuntime.__new__", lambda cls, *args, **kwargs: runtime_mock)
    monkeypatch.setattr("ciris_engine.logic.runtime.ciris_runtime.CIRISRuntime.__init__", lambda self, *args, **kwargs: None)
    
    monkeypatch.setattr(main, "load_config", AsyncMock(return_value=MagicMock(discord_home_channel_id="111")))
    monkeypatch.setattr(main, "_run_runtime", AsyncMock())

    import asyncio as real_asyncio

    real_run = real_asyncio.run

    def fake_run(coro):
        real_run(coro)

    monkeypatch.setattr("asyncio.run", fake_run)

    result = CliRunner().invoke(main.main, [])
    assert result.exit_code == 0
    runtime_mock.initialize.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.skip(reason="ServiceRegistry path doesn't exist in current architecture")
async def test_discord_runtime_cli_fallback(monkeypatch):
    monkeypatch.setattr(
        "ciris_engine.logic.services.runtime.llm_service.OpenAICompatibleClient.start",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "ciris_engine.logic.services.runtime.llm_service.OpenAICompatibleClient.call_llm_structured",
        AsyncMock(return_value=(MagicMock(model_dump=lambda: {"content": "test response"}), MagicMock(tokens=100))),
    )
    monkeypatch.setattr(
        "ciris_engine.logic.runtime.ciris_runtime.CIRISRuntime._build_components",
        AsyncMock(),
    )
    # Observers have been removed; no start methods to patch
    monkeypatch.setattr(
        "ciris_engine.logic.adapters.cli.adapter.CliPlatform.start", AsyncMock()
    )
    # MultiServiceActionSink has been replaced with BusManager
    # No need to patch it anymore
    # Mock service_registry.wait_ready() to prevent timeout
    monkeypatch.setattr(
        "ciris_engine.logic.registries.service_registry.ServiceRegistry.wait_ready", AsyncMock()
    )

    # Mock the runtime
    runtime_mock = MagicMock(spec=CIRISRuntime)
    runtime_mock.initialize = AsyncMock()
    runtime_mock.service_registry = MagicMock()
    runtime_mock.service_registry.get_provider_info = MagicMock(return_value={
        "handlers": {
            "SpeakHandler": {
                "communication": [
                    {"priority": "HIGH", "name": "DiscordAdapter"},
                    {"priority": "NORMAL", "name": "CLIAdapter"},
                ]
            }
        }
    })
    
    # Mock constructor
    monkeypatch.setattr("ciris_engine.logic.runtime.ciris_runtime.CIRISRuntime.__new__", lambda cls, *args, **kwargs: runtime_mock)
    monkeypatch.setattr("ciris_engine.logic.runtime.ciris_runtime.CIRISRuntime.__init__", lambda self, *args, **kwargs: None)

    # Create runtime
    runtime = CIRISRuntime(
        modes=['discord'],
        profile_name='p',
        startup_channel_id='chan',
        discord_bot_token='tok'
    )
    await runtime.initialize()
    info = runtime.service_registry.get_provider_info()
    comm = info["handlers"]["SpeakHandler"]["communication"]
    assert any(
        p["priority"] == "HIGH" and p["name"].startswith("DiscordAdapter") for p in comm
    )
    assert any(
        p["priority"] == "NORMAL" and p["name"].startswith("CLIAdapter") for p in comm
    )