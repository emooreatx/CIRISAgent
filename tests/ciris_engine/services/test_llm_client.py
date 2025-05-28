import os
import types
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from ciris_engine.services.llm_client import CIRISLLMClient

class DummyConfig:
    api_key_env_var = "OPENAI_API_KEY"
    base_url = "https://api.test.com"
    model_name = "gpt-test"
    timeout_seconds = 30
    max_retries = 2
    instructor_mode = "TOOLS"

class DummyAppConfig:
    class LLMServices:
        class OpenAI:
            api_key_env_var = "OPENAI_API_KEY"
            base_url = "https://api.test.com"
            model_name = "gpt-test"
            timeout_seconds = 30
            max_retries = 2
            instructor_mode = "TOOLS"
        openai = OpenAI()
    llm_services = LLMServices()

def make_env(api_key=None, base_url=None, model_name=None):
    if api_key is not None:
        os.environ["OPENAI_API_KEY"] = api_key
    else:
        os.environ.pop("OPENAI_API_KEY", None)
    if base_url is not None:
        os.environ["OPENAI_BASE_URL"] = base_url
    else:
        os.environ.pop("OPENAI_BASE_URL", None)
    if model_name is not None:
        os.environ["OPENAI_MODEL_NAME"] = model_name
    else:
        os.environ.pop("OPENAI_MODEL_NAME", None)

@pytest.fixture(autouse=True)
def clear_env():
    yield
    for var in ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL_NAME"]:
        os.environ.pop(var, None)

@patch("ciris_engine.services.llm_client.AsyncOpenAI")
@patch("ciris_engine.services.llm_client.instructor.patch")
@patch("ciris_engine.services.llm_client.get_config")
def test_init_env_priority(mock_get_config, mock_patch, mock_async_openai):
    mock_get_config.return_value = DummyAppConfig()
    mock_patch.return_value = MagicMock()
    mock_async_openai.return_value = MagicMock()
    make_env(api_key="env-key", base_url="https://env-base", model_name="env-model")
    client = CIRISLLMClient()
    assert client.model_name == "env-model"
    mock_async_openai.assert_called_with(
        api_key="env-key", base_url="https://env-base", timeout=30, max_retries=0
    )
    mock_patch.assert_called()

@patch("ciris_engine.services.llm_client.AsyncOpenAI")
@patch("ciris_engine.services.llm_client.instructor.patch")
@patch("ciris_engine.services.llm_client.get_config")
def test_init_config_fallback(mock_get_config, mock_patch, mock_async_openai):
    mock_get_config.return_value = DummyAppConfig()
    mock_patch.return_value = MagicMock()
    mock_async_openai.return_value = MagicMock()
    make_env(api_key=None, base_url="https://api.test.com", model_name=None)  # Ensure base_url matches assertion
    client = CIRISLLMClient()
    assert client.model_name == "gpt-test"
    mock_async_openai.assert_called_with(
        api_key=None, base_url="https://api.test.com", timeout=30, max_retries=0
    )
    mock_patch.assert_called()

@patch("ciris_engine.services.llm_client.AsyncOpenAI")
@patch("ciris_engine.services.llm_client.instructor.patch")
def test_init_with_config_obj(mock_patch, mock_async_openai):
    mock_patch.return_value = MagicMock()
    mock_async_openai.return_value = MagicMock()
    config = DummyConfig()
    make_env(api_key=None, base_url="https://api.test.com", model_name=None)  # Ensure base_url matches assertion
    client = CIRISLLMClient(config)
    assert client.model_name == "gpt-test"
    mock_async_openai.assert_called_with(
        api_key=None, base_url="https://api.test.com", timeout=30, max_retries=0
    )
    mock_patch.assert_called()

@patch("ciris_engine.services.llm_client.AsyncOpenAI")
@patch("ciris_engine.services.llm_client.instructor.patch", side_effect=Exception("fail-patch"))
def test_instructor_patch_fallback(mock_patch, mock_async_openai):
    mock_async_openai.return_value = MagicMock()
    config = DummyConfig()
    client = CIRISLLMClient(config)
    assert client.instruct_client == client.client

@pytest.mark.parametrize("raw,expected", [
    ("""{'foo': 1}""", {"foo": 1}),
    ('```json\n{"bar": 2}\n```', {"bar": 2}),
    ("no json here", {"error": "Failed to parse JSON. Raw content snippet: no json here..."}),
    ("""{'baz': 3}""", {"baz": 3}),
    ("""{'bad': 1,}""", {"error": "Failed to parse JSON. Raw content snippet: {'bad': 1,..."}),
])
def test_extract_json(raw, expected):
    result = CIRISLLMClient.extract_json(raw)
    if "error" in expected:
        assert "error" in result
    else:
        assert result == expected

@pytest.mark.asyncio
@patch("ciris_engine.services.llm_client.AsyncOpenAI")
@patch("ciris_engine.services.llm_client.instructor.patch")
async def test_call_llm_raw_and_structured(mock_patch, mock_async_openai):
    mock_client = MagicMock()
    mock_async_openai.return_value = mock_client
    mock_patch.return_value = mock_client
    config = DummyConfig()
    client = CIRISLLMClient(config)
    # Mock chat.completions.create for raw
    mock_client.chat.completions.create = AsyncMock(return_value=types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="hello world"))]
    ))
    out = await client.call_llm_raw([{"role": "user", "content": "hi"}])
    assert out == "hello world"
    # Mock for structured
    class DummyModel:
        __name__ = "DummyModel"
    mock_client.chat.completions.create = AsyncMock(return_value="model-out")
    client.instruct_client = mock_client
    out2 = await client.call_llm_structured([{"role": "user", "content": "hi"}], DummyModel)
    assert out2 == "model-out"
