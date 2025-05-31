import pytest
from unittest.mock import AsyncMock, MagicMock
from ciris_engine.runtime.cli_runtime import CLIRuntime
from ciris_engine.adapters.cli.cli_adapter import CLIAdapter
from ciris_engine.adapters.cli.cli_observer import CLIObserver

@pytest.mark.asyncio
async def test_cli_runtime_initialization(monkeypatch):
    monkeypatch.setattr("ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.start", AsyncMock())
    monkeypatch.setattr(
        "ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.get_client",
        MagicMock(return_value=MagicMock(instruct_client=None, client=None, model_name="test"))
    )
    monkeypatch.setattr("ciris_engine.runtime.ciris_runtime.CIRISRuntime._build_components", AsyncMock())
    monkeypatch.setattr(
        "ciris_engine.runtime.cli_runtime.CLIObserver.start", AsyncMock()
    )
    monkeypatch.setattr(
        "ciris_engine.runtime.cli_runtime.CLIAdapter.start", AsyncMock()
    )
    monkeypatch.setattr(
        "ciris_engine.runtime.cli_runtime.MultiServiceActionSink.start", AsyncMock()
    )
    monkeypatch.setattr(
        "ciris_engine.runtime.cli_runtime.MultiServiceDeferralSink.start", AsyncMock()
    )

    runtime = CLIRuntime(profile_name="test_profile", interactive=False)
    await runtime.initialize()
    assert runtime.profile_name == "test_profile"
    assert isinstance(runtime.io_adapter, CLIAdapter)
    assert isinstance(runtime.cli_observer, CLIObserver)

@pytest.mark.asyncio
async def test_cli_message_processing(monkeypatch):
    monkeypatch.setattr("ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.start", AsyncMock())
    monkeypatch.setattr(
        "ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.get_client",
        MagicMock(return_value=MagicMock(instruct_client=None, client=None, model_name="test")),
    )
    monkeypatch.setattr("ciris_engine.runtime.ciris_runtime.CIRISRuntime._build_components", AsyncMock())
    monkeypatch.setattr("ciris_engine.runtime.cli_runtime.CLIObserver.start", AsyncMock())
    monkeypatch.setattr("ciris_engine.runtime.cli_runtime.CLIAdapter.start", AsyncMock())
    monkeypatch.setattr("ciris_engine.runtime.cli_runtime.MultiServiceActionSink.start", AsyncMock())
    monkeypatch.setattr("ciris_engine.runtime.cli_runtime.MultiServiceDeferralSink.start", AsyncMock())

    observe_mock = AsyncMock()
    monkeypatch.setattr(CLIRuntime, "_handle_observe_event", observe_mock)

    runtime = CLIRuntime(profile_name="default", interactive=False)
    await runtime.initialize()

    from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage

    msg = IncomingMessage(
        message_id="test_1",
        content="Hello CLI",
        author_id="test_user",
        author_name="Test User",
        channel_id="cli",
    )

    await runtime.cli_observer.handle_incoming_message(msg)

    observe_mock.assert_awaited_once()
    await runtime.shutdown()
