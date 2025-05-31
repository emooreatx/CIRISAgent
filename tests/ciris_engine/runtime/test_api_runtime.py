import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.runtime.api_runtime import APIRuntime


@pytest.mark.asyncio
async def test_api_runtime_initializes(monkeypatch):
    monkeypatch.setattr("ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.start", AsyncMock())
    monkeypatch.setattr(
        "ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.get_client",
        AsyncMock(return_value=MagicMock(instruct_client=None, client=None, model_name="test")),
    )
    monkeypatch.setattr(
        "ciris_engine.runtime.ciris_runtime.CIRISRuntime._build_components",
        AsyncMock(),
    )
    runtime = APIRuntime(profile_name="test")
    monkeypatch.setattr(runtime, "_register_api_services", AsyncMock())
    await runtime.initialize()
    runtime._register_api_services.assert_called_once()


