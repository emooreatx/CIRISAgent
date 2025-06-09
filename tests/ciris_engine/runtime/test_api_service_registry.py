import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.runtime.ciris_runtime import CIRISRuntime


@pytest.mark.asyncio
async def test_api_service_registry(monkeypatch):
    """Ensure API mode of CIRISRuntime registers expected services."""
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
    # Mock API adapter components
    monkeypatch.setattr("ciris_engine.adapters.api.adapter.ApiPlatform.start", AsyncMock())
    # Mock service_registry.wait_ready() to prevent timeout
    monkeypatch.setattr(
        "ciris_engine.registries.base.ServiceRegistry.wait_ready", AsyncMock()
    )

    # Use unified runtime with API mode
    runtime = CIRISRuntime(modes=["api"], profile_name="default")
    
    # Mock API-specific tool service
    mock_api_tool_service = MagicMock()
    
    await runtime.initialize()

    info = runtime.service_registry.get_provider_info()
    handlers = info.get("handlers", {})

    # Communication service
    comm = handlers.get("SpeakHandler", {}).get("communication", [])
    assert any("APICommunicationService" in p["name"] for p in comm)

    # Wise authority service
    wa = handlers.get("SpeakHandler", {}).get("wise_authority", [])
    assert any("APIWiseAuthorityService" in p["name"] for p in wa)

    # Tool service (may be registered globally or per handler)
    tool = handlers.get("ToolHandler", {}).get("tool", [])
    global_services = info.get("global_services", {})
    tool_global = global_services.get("tool", [])
    
    has_tool_service = (
        any("APIToolService" in p["name"] or "Tool" in p["name"] for p in tool) or
        any("APIToolService" in p["name"] or "Tool" in p["name"] for p in tool_global)
    )
    assert has_tool_service

    await runtime.shutdown()
