import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ciris_engine.runtime.ciris_runtime import CIRISRuntime


@pytest.mark.asyncio
async def test_cli_service_registry(monkeypatch):
    """Ensure CLI mode of CIRISRuntime registers expected services."""
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
    # Mock CLI adapter components
    monkeypatch.setattr("ciris_engine.adapters.cli.adapter.CLIAdapter.start", AsyncMock())
    monkeypatch.setattr("ciris_engine.sinks.multi_service_sink.MultiServiceActionSink.start", AsyncMock())
    # Mock service_registry.wait_ready() to prevent timeout
    monkeypatch.setattr(
        "ciris_engine.registries.base.ServiceRegistry.wait_ready", AsyncMock()
    )

    # Use unified runtime with CLI mode
    runtime = CIRISRuntime(modes=["cli"], profile_name="default")
    await runtime.initialize()

    info = runtime.service_registry.get_provider_info()
    handlers = info.get("handlers", {})

    # Check communication service registration
    speak_comm = handlers.get("SpeakHandler", {}).get("communication", [])
    assert any("CLIAdapter" in p["name"] for p in speak_comm)

    # Observer service (now registered as communication)
    observe_comm = handlers.get("ObserveHandler", {}).get("communication", [])
    assert any("CLIAdapter" in p["name"] for p in observe_comm)

    # Tool service
    tool_services = handlers.get("ToolHandler", {}).get("tool", [])
    assert any("CLIToolService" in p["name"] or "CLIAdapter" in p["name"] for p in tool_services)

    # Wise authority service
    wa_services = handlers.get("DeferHandler", {}).get("wise_authority", [])
    assert any("CLIWiseAuthorityService" in p["name"] or "CLIAdapter" in p["name"] for p in wa_services)

    await runtime.shutdown()
