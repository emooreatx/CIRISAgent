import os
import types
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from ciris_engine.services.llm_service import OpenAICompatibleClient

class DummyConfig:
    api_key = None  # Explicitly set for fallback tests
    api_key_env_var = "OPENAI_API_KEY"
    base_url = None  # Explicitly set for fallback tests
    model_name = None  # Explicitly set for fallback tests
    timeout_seconds = 30
    max_retries = 2
    instructor_mode = "TOOLS"

class DummyAppConfig:
    class LLMServices:
        class OpenAI:
            api_key = None  # Explicitly set for fallback tests
            api_key_env_var = "OPENAI_API_KEY"
            base_url = None  # Explicitly set for fallback tests
            model_name = None  # Explicitly set for fallback tests
            timeout_seconds = 30
            max_retries = 2
            instructor_mode = "TOOLS"
        openai = OpenAI()
    llm_services = LLMServices()

def make_env(api_key=None, base_url=None, model_name=None):
    # Clear all relevant env vars first
    for var in ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_BASE", "OPENAI_MODEL_NAME"]:
        if var in os.environ:
            del os.environ[var]
    if api_key is not None:
        os.environ["OPENAI_API_KEY"] = api_key
    if base_url is not None:
        os.environ["OPENAI_BASE_URL"] = base_url
    if model_name is not None:
        os.environ["OPENAI_MODEL_NAME"] = model_name

@pytest.fixture(autouse=True)
def clear_env():
    for var in ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_BASE", "OPENAI_MODEL_NAME"]:
        if var in os.environ:
            del os.environ[var]
    yield
    for var in ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_BASE", "OPENAI_MODEL_NAME"]:
        if var in os.environ:
            del os.environ[var]

@patch("ciris_engine.services.llm_service.AsyncOpenAI")
@patch("ciris_engine.services.llm_service.instructor.from_openai")
@patch("ciris_engine.services.llm_service.get_config")
def test_init_env_priority(mock_get_config, mock_from_openai, mock_async_openai):
    mock_get_config.return_value = DummyAppConfig()
    mock_from_openai.return_value = MagicMock()
    mock_async_openai.return_value = MagicMock()
    # Set config values to None to force env fallback
    DummyAppConfig.LLMServices.OpenAI.api_key = None
    DummyAppConfig.LLMServices.OpenAI.base_url = None
    DummyAppConfig.LLMServices.OpenAI.model_name = None
    make_env(api_key="env-key", base_url="https://env-base", model_name="env-model")
    client = OpenAICompatibleClient()
    # Since config.api_key is None, should fall back to mock LLM
    assert client.model_name == "mock-model"
    # AsyncOpenAI should not be called since we're using mock
    mock_async_openai.assert_not_called()
    mock_from_openai.assert_not_called()

@patch("ciris_engine.services.llm_service.AsyncOpenAI")
@patch("ciris_engine.services.llm_service.instructor.from_openai")
@patch("ciris_engine.services.llm_service.get_config")
def test_init_config_fallback(mock_get_config, mock_from_openai, mock_async_openai):
    mock_get_config.return_value = DummyAppConfig()
    mock_from_openai.return_value = MagicMock()
    mock_async_openai.return_value = MagicMock()
    # Set config values to test AppConfig priority
    DummyAppConfig.LLMServices.OpenAI.api_key = None
    DummyAppConfig.LLMServices.OpenAI.base_url = "https://api.test.com"
    DummyAppConfig.LLMServices.OpenAI.model_name = "gpt-test"
    make_env(api_key=None, base_url="https://env-base", model_name=None)
    client = OpenAICompatibleClient()
    # Since config.api_key is None, should fall back to mock LLM
    assert client.model_name == "mock-model"
    # AsyncOpenAI should not be called since we're using mock
    mock_async_openai.assert_not_called()
    mock_from_openai.assert_not_called()

@patch("ciris_engine.services.llm_service.AsyncOpenAI")
@patch("ciris_engine.services.llm_service.instructor.from_openai")
@patch("ciris_engine.services.llm_service.get_config")
def test_init_with_api_key(mock_get_config, mock_from_openai, mock_async_openai):
    mock_get_config.return_value = DummyAppConfig()
    mock_from_openai.return_value = MagicMock()
    mock_async_openai.return_value = MagicMock()
    # Set config values with API key to test real OpenAI client creation
    DummyAppConfig.LLMServices.OpenAI.api_key = "test-api-key"
    DummyAppConfig.LLMServices.OpenAI.base_url = "https://api.test.com"
    DummyAppConfig.LLMServices.OpenAI.model_name = "gpt-test"
    make_env(api_key=None, base_url=None, model_name=None)
    client = OpenAICompatibleClient()
    # Since config.api_key is provided, should use real OpenAI client
    assert client.model_name == "gpt-test"
    # AsyncOpenAI should be called with config values
    mock_async_openai.assert_called_with(
        api_key="test-api-key", base_url="https://api.test.com", timeout=30, max_retries=0
    )
    mock_from_openai.assert_called()

@patch("ciris_engine.services.llm_service.AsyncOpenAI")
@patch("ciris_engine.services.llm_service.instructor.from_openai")
def test_init_with_config_obj(mock_from_openai, mock_async_openai):
    mock_from_openai.return_value = MagicMock()
    mock_async_openai.return_value = MagicMock()
    config = DummyConfig()
    # Set config values to test AppConfig priority
    config.api_key = None
    config.base_url = "https://api.test.com"
    config.model_name = "gpt-test"
    make_env(api_key=None, base_url="https://env-base", model_name=None)
    client = OpenAICompatibleClient(config)
    # Since config.api_key is None, should fall back to mock LLM
    assert client.model_name == "mock-model"
    # AsyncOpenAI should not be called since we're using mock
    mock_async_openai.assert_not_called()
    mock_from_openai.assert_not_called()

@patch("ciris_engine.services.llm_service.AsyncOpenAI")
@patch("ciris_engine.services.llm_service.instructor.from_openai", side_effect=Exception("fail-from_openai"))
def test_instructor_patch_fallback(mock_from_openai, mock_async_openai):
    mock_async_openai.return_value = MagicMock()
    config = DummyConfig()
    # Provide a valid API key so it tries to create real OpenAI client
    config.api_key = "test-api-key"
    with pytest.raises(Exception):
        client = OpenAICompatibleClient(config)

@pytest.mark.parametrize("raw,expected", [
    ("""{'foo': 1}""", {"foo": 1}),
    ('```json\n{"bar": 2}\n```', {"bar": 2}),
    ("no json here", {"error": "Failed to parse JSON. Raw content snippet: no json here"}),
    ("""{'baz': 3}""", {"baz": 3}),
    ("""{'bad': 1,}""", {"error": "Failed to parse JSON. Raw content snippet: {'bad': 1,"}),
])
def test_extract_json(raw, expected):
    result = OpenAICompatibleClient.extract_json(raw)
    if "error" in expected:
        assert "error" in result
    else:
        assert result == expected

@pytest.mark.asyncio
@patch("ciris_engine.services.llm_service.AsyncOpenAI")
@patch("ciris_engine.services.llm_service.instructor.from_openai")
async def test_call_llm_structured(mock_from_openai, mock_async_openai):
    from pydantic import BaseModel
    
    class TestModel(BaseModel):
        response: str = "test"
        
    mock_client = MagicMock()
    mock_async_openai.return_value = mock_client
    mock_instruct_client = MagicMock()
    mock_from_openai.return_value = mock_instruct_client
    config = DummyConfig()
    # Provide a valid API key so it uses the real OpenAI client (which is mocked)
    config.api_key = "test-api-key"
    client = OpenAICompatibleClient(config)
    
    # Mock the instructor client's chat.completions.create
    structured_response = TestModel(response="hello world")
    mock_instruct_client.chat.completions.create = AsyncMock(return_value=structured_response)
    
    result, usage = await client.call_llm_structured(
        messages=[{"role": "user", "content": "hi"}],
        response_model=TestModel
    )
    assert result.response == "hello world"  # type: ignore[attr-defined]
    assert usage.tokens_used == 0  # Mock doesn't set real usage
