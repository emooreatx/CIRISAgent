import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.runtime.api_runtime import APIRuntime


@pytest.mark.asyncio
async def test_api_service_registry(monkeypatch):
    """Ensure APIRuntime registers expected services."""
    monkeypatch.setattr(
        "ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.start",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.get_client",
        MagicMock(return_value=MagicMock(instruct_client=None, client=None, model_name="test")),
    )
    monkeypatch.setattr(
        "ciris_engine.runtime.ciris_runtime.CIRISRuntime._build_components",
        AsyncMock(),
    )
    monkeypatch.setattr("ciris_engine.adapters.api.api_observer.APIObserver.start", AsyncMock())
    # Mock service_registry.wait_ready() to prevent timeout
    monkeypatch.setattr(
        "ciris_engine.registries.base.ServiceRegistry.wait_ready", AsyncMock()
    )

    runtime = APIRuntime(profile_name="default")
    runtime.api_tool_service = MagicMock()
    await runtime.initialize()

    info = runtime.service_registry.get_provider_info()
    handlers = info.get("handlers", {})

    # Communication service
    comm = handlers.get("SpeakHandler", {}).get("communication", [])
    assert any(p["name"].startswith("APIAdapter") for p in comm)

    # Wise authority service
    wa = handlers.get("SpeakHandler", {}).get("wise_authority", [])
    assert any(p["name"].startswith("APIAdapter") for p in wa)

    # Tool service
    tool = handlers.get("ToolHandler", {}).get("tool", [])
    assert any(p["name"].startswith("MagicMock") for p in tool)

    await runtime.shutdown()
