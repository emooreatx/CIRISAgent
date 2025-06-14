import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.runtime.ciris_runtime import CIRISRuntime


@pytest.mark.asyncio
async def test_api_service_registry(monkeypatch):
    """Ensure API mode of CIRISRuntime has service registry structure (adapter doesn't register services)."""
    from ciris_engine.schemas.foundational_schemas_v1 import ResourceUsage
    from pydantic import BaseModel
    
    class MockResponse(BaseModel):
        content: str = "test response"
    
    mock_resource_usage = ResourceUsage(
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=None,
        cost_usd=0.001
    )
    
    monkeypatch.setattr(
        "ciris_engine.services.llm_service.OpenAICompatibleClient.start",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "ciris_engine.services.llm_service.OpenAICompatibleClient.call_llm_structured",
        AsyncMock(return_value=(MockResponse(), mock_resource_usage)),
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
    runtime = CIRISRuntime(adapter_types=["api"], profile_name="default")
    
    await runtime.initialize()

    # Test that service registry exists and has proper structure
    # API adapter intentionally doesn't register services - it acts as transport layer
    info = runtime.service_registry.get_provider_info()
    
    # Verify the registry structure exists
    assert isinstance(info, dict)
    assert "handlers" in info
    assert "global_services" in info
    
    # When _build_components is mocked, no services are registered
    # This validates the registry can be queried without requiring specific services
    handlers = info.get("handlers", {})
    global_services = info.get("global_services", {})
    
    # Both should be empty dicts when _build_components is mocked
    assert isinstance(handlers, dict)
    assert isinstance(global_services, dict)

    await runtime.shutdown()
