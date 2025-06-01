import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.runtime.cli_runtime import CLIRuntime


@pytest.mark.asyncio
async def test_cli_service_registry(monkeypatch):
    """Ensure CLIRuntime registers expected services."""
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
    monkeypatch.setattr("ciris_engine.runtime.cli_runtime.CLIObserver.start", AsyncMock())
    monkeypatch.setattr("ciris_engine.runtime.cli_runtime.CLIAdapter.start", AsyncMock())
    monkeypatch.setattr("ciris_engine.sinks.multi_service_sink.MultiServiceActionSink.start", AsyncMock())

    runtime = CLIRuntime(profile_name="default", interactive=False)
    await runtime.initialize()

    info = runtime.service_registry.get_provider_info()
    handlers = info.get("handlers", {})

    # Check communication service registration
    speak_comm = handlers.get("SpeakHandler", {}).get("communication", [])
    assert any(p["name"].startswith("CLIAdapter") for p in speak_comm)

    # Observer service
    observe_observers = handlers.get("ObserveHandler", {}).get("observer", [])
    assert any(p["name"].startswith("CLIObserver") for p in observe_observers)

    # Tool service
    tool_services = handlers.get("ToolHandler", {}).get("tool", [])
    assert any(p["name"].startswith("CLIToolService") for p in tool_services)

    # Wise authority service
    wa_services = handlers.get("DeferHandler", {}).get("wise_authority", [])
    assert any(p["name"].startswith("CLIWiseAuthorityService") for p in wa_services)

    await runtime.shutdown()
