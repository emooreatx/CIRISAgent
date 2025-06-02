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
        "ciris_engine.sinks.multi_service_sink.MultiServiceActionSink.start", AsyncMock()
    )
    # Mock service_registry.wait_ready() to prevent timeout
    monkeypatch.setattr(
        "ciris_engine.registries.base.ServiceRegistry.wait_ready", AsyncMock()
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
    monkeypatch.setattr("ciris_engine.sinks.multi_service_sink.MultiServiceActionSink.start", AsyncMock())
    # Mock service_registry.wait_ready() to prevent timeout
    monkeypatch.setattr(
        "ciris_engine.registries.base.ServiceRegistry.wait_ready", AsyncMock()
    )

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
    assert runtime.cli_observer._history and runtime.cli_observer._history[-1].message_id == "test_1"
    await runtime.shutdown()
