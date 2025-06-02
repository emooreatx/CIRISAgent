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


@pytest.mark.asyncio
async def test_api_routes_setup(monkeypatch):
    monkeypatch.setattr("ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.start", AsyncMock())
    monkeypatch.setattr(
        "ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.get_client",
        MagicMock(return_value=MagicMock(instruct_client=None, client=None, model_name="test")),
    )
    monkeypatch.setattr("ciris_engine.runtime.ciris_runtime.CIRISRuntime._build_components", AsyncMock())
    monkeypatch.setattr("ciris_engine.adapters.api.api_observer.APIObserver.start", AsyncMock())

    runtime = APIRuntime(profile_name="default")
    await runtime.initialize()

    routes = [r.resource.canonical for r in runtime.app.router.routes()]
    assert "/v1/messages" in routes
    assert "/v1/status" in routes

    await runtime.shutdown()


@pytest.mark.asyncio
async def test_handle_message(monkeypatch):
    monkeypatch.setattr("ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.start", AsyncMock())
    monkeypatch.setattr(
        "ciris_engine.adapters.openai_compatible_llm.OpenAICompatibleLLM.get_client",
        MagicMock(return_value=MagicMock(instruct_client=None, client=None, model_name="test")),
    )
    monkeypatch.setattr("ciris_engine.runtime.ciris_runtime.CIRISRuntime._build_components", AsyncMock())
    monkeypatch.setattr("ciris_engine.adapters.api.api_observer.APIObserver.start", AsyncMock())

    runtime = APIRuntime(profile_name="default")
    await runtime.initialize()

    # Mock the api_observer.handle_incoming_message method instead of message_queue.enqueue
    runtime.api_observer.handle_incoming_message = AsyncMock()

    class DummyRequest:
        def __init__(self, data):
            self._data = data
        async def json(self):
            return self._data

    req = DummyRequest({"content": "hi"})
    resp = await runtime._handle_message(req)
    assert resp.status == 200
    runtime.api_observer.handle_incoming_message.assert_awaited_once()
    await runtime.shutdown()
