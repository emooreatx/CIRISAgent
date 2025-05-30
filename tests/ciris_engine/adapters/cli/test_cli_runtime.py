import pytest
from unittest.mock import AsyncMock, MagicMock
from ciris_engine.adapters.cli.cli_runtime import CLIRuntime
from ciris_engine.adapters.cli.cli_adapter import CLIAdapter
from ciris_engine.adapters.cli.cli_observer import CLIObserver

@pytest.mark.asyncio
async def test_cli_runtime_initialization(monkeypatch):
    monkeypatch.setattr("ciris_engine.services.llm_service.LLMService.start", AsyncMock())
    monkeypatch.setattr(
        "ciris_engine.services.llm_service.LLMService.get_client",
        MagicMock(return_value=MagicMock(instruct_client=None, client=None, model_name="test"))
    )
    monkeypatch.setattr("ciris_engine.runtime.ciris_runtime.CIRISRuntime._build_components", AsyncMock())
    runtime = CLIRuntime(profile_name="test_profile", interactive=False)
    await runtime.initialize()
    assert runtime.profile_name == "test_profile"
    assert isinstance(runtime.io_adapter, CLIAdapter)
    assert isinstance(runtime.cli_observer, CLIObserver)
