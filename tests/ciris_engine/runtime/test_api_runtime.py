import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.runtime.api_runtime import APIRuntime
from ciris_engine.runtime.runtime_interface import RuntimeInterface

@pytest.mark.asyncio
async def test_api_runtime_initialization_calls_register(monkeypatch):
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
    register_mock = AsyncMock()
    monkeypatch.setattr(APIRuntime, "_register_api_services", register_mock)

    runtime = APIRuntime(profile_name="test_profile")
    await runtime.initialize()

    register_mock.assert_awaited_once()
    assert runtime.profile_name == "test_profile"


def test_api_runtime_implements_interface():
    runtime = APIRuntime()
    assert isinstance(runtime, RuntimeInterface)

