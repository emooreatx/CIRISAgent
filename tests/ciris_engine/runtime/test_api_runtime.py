import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.runtime.ciris_runtime import CIRISRuntime
from ciris_engine.runtime.runtime_interface import RuntimeInterface

@pytest.mark.asyncio
async def test_api_runtime_initialization_with_api_mode(monkeypatch):
    """Test that CIRISRuntime with API mode initializes correctly."""
    monkeypatch.setattr(
        "ciris_engine.services.llm_service.OpenAICompatibleClient.start",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "ciris_engine.services.llm_service.OpenAICompatibleClient.call_llm_structured",
        AsyncMock(return_value=(MagicMock(), MagicMock())),
    )
    monkeypatch.setattr(
        "ciris_engine.runtime.ciris_runtime.CIRISRuntime._build_components",
        AsyncMock(),
    )
    # Mock service_registry.wait_ready() to prevent timeout
    monkeypatch.setattr(
        "ciris_engine.registries.base.ServiceRegistry.wait_ready", AsyncMock()
    )
    
    # Mock API adapter loading
    mock_adapter_start = AsyncMock()
    monkeypatch.setattr("ciris_engine.adapters.api.adapter.ApiPlatform.start", mock_adapter_start)

    runtime = CIRISRuntime(modes=["api"], profile_name="test_profile")
    await runtime.initialize()

    # Verify runtime initialized correctly
    assert runtime.profile_name == "test_profile"
    assert len(runtime.adapters) == 1  # Should have one API adapter
    assert "api" in [adapter.__class__.__module__.split('.')[-2] for adapter in runtime.adapters if hasattr(adapter, '__class__')]


def test_api_runtime_implements_interface():
    """Test that CIRISRuntime with API mode implements RuntimeInterface."""
    runtime = CIRISRuntime(modes=["api"])
    assert isinstance(runtime, RuntimeInterface)


@pytest.mark.asyncio 
async def test_api_adapter_service_registration(monkeypatch):
    """Test that API adapter can be initialized without services (by design)."""
    monkeypatch.setattr("ciris_engine.services.llm_service.OpenAICompatibleClient.start", AsyncMock())
    monkeypatch.setattr(
        "ciris_engine.services.llm_service.OpenAICompatibleClient.call_llm_structured",
        AsyncMock(return_value=(MagicMock(), MagicMock())),
    )
    monkeypatch.setattr("ciris_engine.runtime.ciris_runtime.CIRISRuntime._build_components", AsyncMock())
    monkeypatch.setattr("ciris_engine.adapters.api.adapter.ApiPlatform.start", AsyncMock())
    # Mock service_registry.wait_ready() to prevent timeout
    monkeypatch.setattr(
        "ciris_engine.registries.base.ServiceRegistry.wait_ready", AsyncMock()
    )

    runtime = CIRISRuntime(modes=["api"], profile_name="default")
    await runtime.initialize()

    # Verify service registry has been created
    assert runtime.service_registry is not None
    
    # API adapter is designed not to register services - it acts as a transport layer
    # When _build_components is mocked, no services get registered, which is expected
    info = runtime.service_registry.get_provider_info()
    # This test verifies the registry exists and can be queried, but doesn't require services
    assert isinstance(info, dict)
    assert "handlers" in info
    assert "global_services" in info

    await runtime.shutdown()


@pytest.mark.asyncio
async def test_api_mode_adapter_lifecycle(monkeypatch):
    """Test API adapter lifecycle management through CIRISRuntime."""
    monkeypatch.setattr("ciris_engine.services.llm_service.OpenAICompatibleClient.start", AsyncMock())
    monkeypatch.setattr(
        "ciris_engine.services.llm_service.OpenAICompatibleClient.call_llm_structured",
        AsyncMock(return_value=(MagicMock(), MagicMock())),
    )
    monkeypatch.setattr("ciris_engine.runtime.ciris_runtime.CIRISRuntime._build_components", AsyncMock())
    
    # Mock API adapter methods
    mock_start = AsyncMock()
    mock_stop = AsyncMock()
    monkeypatch.setattr("ciris_engine.adapters.api.adapter.ApiPlatform.start", mock_start)
    monkeypatch.setattr("ciris_engine.adapters.api.adapter.ApiPlatform.stop", mock_stop)
    
    # Mock service_registry.wait_ready() to prevent timeout
    monkeypatch.setattr(
        "ciris_engine.registries.base.ServiceRegistry.wait_ready", AsyncMock()
    )

    runtime = CIRISRuntime(modes=["api"], profile_name="default")
    await runtime.initialize()
    
    # Verify adapter was started
    mock_start.assert_called()
    
    await runtime.shutdown()
    
    # Verify adapter was stopped  
    mock_stop.assert_called()
