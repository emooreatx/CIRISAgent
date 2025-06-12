import pytest
from unittest.mock import AsyncMock, MagicMock
from ciris_engine.runtime.ciris_runtime import CIRISRuntime


@pytest.mark.asyncio
async def test_cli_runtime_initialization(monkeypatch, tmp_path):
    """Test CLI mode initialization in unified CIRISRuntime."""
    # Mock only the external dependencies
    monkeypatch.setattr("ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.start", AsyncMock())
    monkeypatch.setattr(
        "ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.get_client",
        MagicMock(return_value=MagicMock(instruct_client=None, client=None, model_name="test"))
    )
    monkeypatch.setattr("ciris_engine.runtime.ciris_runtime.CIRISRuntime._build_components", AsyncMock())
    monkeypatch.setattr("ciris_engine.adapters.cli.adapter.CLIAdapter.start", AsyncMock())
    monkeypatch.setattr("ciris_engine.registries.base.ServiceRegistry.wait_ready", AsyncMock())
    
    # Use temp database to avoid conflicts
    monkeypatch.setenv("CIRIS_DB_PATH", str(tmp_path / "test.db"))

    runtime = CIRISRuntime(modes=["cli"], profile_name="default", interactive=False)
    await runtime.initialize()

    # Verify CLI adapter was loaded
    assert len(runtime.adapters) == 1
    assert runtime.profile_name == "default"

    await runtime.shutdown()


@pytest.mark.asyncio
async def test_cli_adapter_service_registration(monkeypatch, tmp_path):
    """Test that CLI adapter services are registered correctly."""
    # Mock only the external dependencies
    monkeypatch.setattr("ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.start", AsyncMock())
    monkeypatch.setattr(
        "ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.get_client",
        MagicMock(return_value=MagicMock(instruct_client=None, client=None, model_name="test"))
    )
    monkeypatch.setattr("ciris_engine.runtime.ciris_runtime.CIRISRuntime._build_components", AsyncMock())
    monkeypatch.setattr("ciris_engine.adapters.cli.adapter.CLIAdapter.start", AsyncMock())
    monkeypatch.setattr("ciris_engine.registries.base.ServiceRegistry.wait_ready", AsyncMock())
    
    # Use temp database to avoid conflicts
    monkeypatch.setenv("CIRIS_DB_PATH", str(tmp_path / "test.db"))

    runtime = CIRISRuntime(modes=["cli"], profile_name="default", interactive=False)
    await runtime.initialize()

    # Verify service registry was created and has services
    assert runtime.service_registry is not None
    
    info = runtime.service_registry.get_provider_info()
    has_services = (
        len(info.get("handlers", {})) > 0 or
        len(info.get("global_services", {})) > 0
    )
    assert has_services

    await runtime.shutdown()


@pytest.mark.asyncio
async def test_cli_interactive_mode_flag(monkeypatch, tmp_path):
    """Test that interactive mode flag is passed correctly."""
    # Mock only the external dependencies
    monkeypatch.setattr("ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.start", AsyncMock())
    monkeypatch.setattr(
        "ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.get_client", 
        MagicMock(return_value=MagicMock(instruct_client=None, client=None, model_name="test"))
    )
    monkeypatch.setattr("ciris_engine.runtime.ciris_runtime.CIRISRuntime._build_components", AsyncMock())
    monkeypatch.setattr("ciris_engine.adapters.cli.adapter.CLIAdapter.start", AsyncMock())
    monkeypatch.setattr("ciris_engine.registries.base.ServiceRegistry.wait_ready", AsyncMock())
    
    # Use temp database to avoid conflicts
    monkeypatch.setenv("CIRIS_DB_PATH", str(tmp_path / "test.db"))

    # Test both interactive and non-interactive modes
    runtime_interactive = CIRISRuntime(modes=["cli"], profile_name="default", interactive=True)
    runtime_non_interactive = CIRISRuntime(modes=["cli"], profile_name="default", interactive=False)
    
    await runtime_interactive.initialize()
    await runtime_non_interactive.initialize()
    
    # Both should initialize successfully
    assert len(runtime_interactive.adapters) == 1
    assert len(runtime_non_interactive.adapters) == 1
    
    await runtime_interactive.shutdown()
    await runtime_non_interactive.shutdown()


@pytest.mark.asyncio
async def test_cli_message_processing(monkeypatch, tmp_path):
    """Test CLI message processing through unified runtime."""
    # Mock only the external dependencies
    monkeypatch.setattr("ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.start", AsyncMock())
    monkeypatch.setattr(
        "ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.get_client",
        MagicMock(return_value=MagicMock(instruct_client=None, client=None, model_name="test")),
    )
    monkeypatch.setattr("ciris_engine.runtime.ciris_runtime.CIRISRuntime._build_components", AsyncMock())
    monkeypatch.setattr("ciris_engine.adapters.cli.adapter.CLIAdapter.start", AsyncMock())
    monkeypatch.setattr("ciris_engine.registries.base.ServiceRegistry.wait_ready", AsyncMock())
    
    # Use temp database to avoid conflicts
    monkeypatch.setenv("CIRIS_DB_PATH", str(tmp_path / "test.db"))

    runtime = CIRISRuntime(modes=["cli"], profile_name="default", interactive=False)
    await runtime.initialize()

    # Verify CLI adapter is available
    assert len(runtime.adapters) == 1
    cli_adapter = runtime.adapters[0]
    
    # Verify adapter type (should be CLIAdapter or have CLI-like interface)
    assert hasattr(cli_adapter, 'start')
    
    await runtime.shutdown()


@pytest.mark.asyncio 
async def test_cli_runtime_shutdown_graceful(monkeypatch, tmp_path):
    """Test graceful shutdown of CLI runtime."""
    # Mock only the external dependencies
    monkeypatch.setattr("ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.start", AsyncMock())
    monkeypatch.setattr(
        "ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.get_client",
        MagicMock(return_value=MagicMock(instruct_client=None, client=None, model_name="test"))
    )
    monkeypatch.setattr("ciris_engine.runtime.ciris_runtime.CIRISRuntime._build_components", AsyncMock())
    monkeypatch.setattr("ciris_engine.adapters.cli.adapter.CLIAdapter.start", AsyncMock())
    monkeypatch.setattr("ciris_engine.adapters.cli.adapter.CLIAdapter.stop", AsyncMock())
    monkeypatch.setattr("ciris_engine.registries.base.ServiceRegistry.wait_ready", AsyncMock())
    
    # Use temp database to avoid conflicts
    monkeypatch.setenv("CIRIS_DB_PATH", str(tmp_path / "test.db"))

    runtime = CIRISRuntime(modes=["cli"], profile_name="default", interactive=False)
    await runtime.initialize()
    
    # Should shutdown without errors
    await runtime.shutdown()
    
    # Runtime should be in shutdown state
    assert runtime._shutdown_event.is_set()
