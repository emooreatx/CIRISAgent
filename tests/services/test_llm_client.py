import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import os
import json
from openai import AsyncOpenAI # Import the missing class
import openai # Import the openai module itself for direct reference

# Module to test
from ciris_engine.services.llm_client import CIRISLLMClient
from ciris_engine.schemas.config_schemas_v1 import AppConfig, OpenAIConfig, LLMServicesConfig
from pydantic import BaseModel, Field

# --- Test Pydantic Model for structured responses ---
class MockResponseModel(BaseModel):
    message: str
    value: int

# --- Fixtures ---

@pytest.fixture
def mock_openai_config():
    """Provides a default OpenAIConfig instance for tests."""
    return OpenAIConfig(
        model_name="test-model",
        base_url="http://localhost:1234/v1",
        timeout_seconds=10.0,
        max_retries=1,
        api_key_env_var="TEST_OPENAI_API_KEY", # Test will often mock env var
        instructor_mode="TOOLS"
    )

@pytest.fixture
def mock_app_config(mock_openai_config: OpenAIConfig):
    """Provides an AppConfig with the mocked OpenAIConfig."""
    return AppConfig(
        llm_services=LLMServicesConfig(openai=mock_openai_config)
    )

@pytest.fixture
def mock_get_config(monkeypatch, mock_app_config: AppConfig):
    """Mocks config_manager.get_config to return our test AppConfig."""
    monkeypatch.setattr("ciris_engine.services.llm_client.get_config", lambda: mock_app_config)

@pytest.fixture
def mock_async_openai_client():
    """Mocks the AsyncOpenAI client instance and its methods."""
    mock_client = AsyncMock(spec=AsyncOpenAI)
    mock_client.chat = AsyncMock()
    mock_client.chat.completions = AsyncMock()
    mock_client.chat.completions.create = AsyncMock()
    return mock_client

@pytest.fixture
def mock_instructor_patch(monkeypatch):
    """Mocks instructor.patch."""
    mock_patch = MagicMock(return_value=AsyncMock()) # Returns a mock patched client
    # The patched client also needs chat.completions.create
    mock_patch.return_value.chat = AsyncMock()
    mock_patch.return_value.chat.completions = AsyncMock()
    mock_patch.return_value.chat.completions.create = AsyncMock()
    monkeypatch.setattr("ciris_engine.services.llm_client.instructor.patch", mock_patch)
    return mock_patch


# --- Test Cases ---

def test_llm_client_initialization_default_config(mock_get_config, mock_app_config, mock_async_openai_client, mock_instructor_patch, monkeypatch):
    """Test client initialization using config from get_config."""
    # Patch AsyncOpenAI where it's used in the llm_client module
    mock_constructor = MagicMock(return_value=mock_async_openai_client)
    monkeypatch.setattr("ciris_engine.services.llm_client.AsyncOpenAI", mock_constructor)

    # Temporarily remove env vars that could override the mock config
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    monkeypatch.delenv(mock_app_config.llm_services.openai.api_key_env_var, raising=False)
    monkeypatch.delenv("OPENAI_MODEL_NAME", raising=False) # Add this line

    # mock_get_config fixture ensures that get_config() inside CIRISLLMClient returns mock_app_config
    client = CIRISLLMClient()

    # Assert that our mock constructor was called
    assert mock_constructor.call_args is not None
    assert mock_constructor.call_args.kwargs.get("base_url") == mock_app_config.llm_services.openai.base_url
    assert client.model_name == mock_app_config.llm_services.openai.model_name

    mock_instructor_patch.assert_called_once()
    # Check that the original client instance was passed to patch
    assert mock_instructor_patch.call_args[0][0] == mock_async_openai_client
    # Check mode (assuming default TOOLS from mock_openai_config)
    from instructor import Mode
    assert mock_instructor_patch.call_args[1]['mode'] == Mode.TOOLS
    assert client.instruct_client is not None # Should be the patched client

def test_llm_client_initialization_with_env_api_key(mock_get_config, mock_async_openai_client, mock_instructor_patch, monkeypatch):
    """Test client initialization when API key is set via environment variable."""
    # Patch AsyncOpenAI where it's used in the llm_client module
    mock_constructor = MagicMock(return_value=mock_async_openai_client)
    monkeypatch.setattr("ciris_engine.services.llm_client.AsyncOpenAI", mock_constructor)

    test_api_key = "test_env_key_123"
    # Initialize client once to access its config for api_key_env_var
    # This is a bit of a workaround for the test structure.
    # Ideally, the config object itself would be more directly accessible or passed around.
    temp_client_for_config = CIRISLLMClient()
    api_key_env_var_name = temp_client_for_config.config.api_key_env_var
    monkeypatch.setenv(api_key_env_var_name, test_api_key)

    # Temporarily remove other env vars that could interfere
    monkeypatch.delenv("OPENAI_API_KEY", raising=False) # Remove the standard one if it exists
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)

    client = CIRISLLMClient() # Re-initialize after setting env var

    # Assert that our mock constructor was called with the correct args
    mock_constructor.assert_called_with(
        api_key=test_api_key, # Check if env var key was passed
        base_url=client.config.base_url,
        timeout=client.config.timeout_seconds,
        max_retries=0
    )

def test_llm_client_initialization_instructor_mode_json(mock_app_config: AppConfig, mock_async_openai_client, mock_instructor_patch, monkeypatch):
    """Test client initialization with JSON instructor mode."""
    # Patch AsyncOpenAI where it's used in the llm_client module
    mock_constructor = MagicMock(return_value=mock_async_openai_client)
    monkeypatch.setattr("ciris_engine.services.llm_client.AsyncOpenAI", mock_constructor)

    mock_app_config.llm_services.openai.instructor_mode = "JSON" # Override mode
    monkeypatch.setattr("ciris_engine.services.llm_client.get_config", lambda: mock_app_config)

    client = CIRISLLMClient()
    from instructor import Mode
    # Assert that patch was called, and check its arguments more carefully
    assert mock_instructor_patch.call_count == 1
    call_args_list = mock_instructor_patch.call_args_list
    # The first argument to patch should be the mock client instance returned by our mock constructor
    assert call_args_list[0][0][0] == mock_async_openai_client
    # The mode keyword argument should be Mode.JSON
    assert call_args_list[0][1]['mode'] == Mode.JSON


@pytest.mark.asyncio
async def test_call_llm_raw_success(mock_get_config, mock_async_openai_client, mock_instructor_patch, monkeypatch):
    # Patch AsyncOpenAI where it's used in the llm_client module
    mock_constructor = MagicMock(return_value=mock_async_openai_client)
    monkeypatch.setattr("ciris_engine.services.llm_client.AsyncOpenAI", mock_constructor)

    client = CIRISLLMClient()

    # Mock the response from the *mocked* openai client instance
    mock_choice = MagicMock()
    mock_choice.message.content = " Raw LLM response "
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_async_openai_client.chat.completions.create.return_value = mock_completion
    
    messages = [{"role": "user", "content": "Test prompt"}]
    response = await client.call_llm_raw(messages=messages, max_tokens=50, temperature=0.5)
    
    mock_async_openai_client.chat.completions.create.assert_awaited_once_with(
        model=client.model_name,
        messages=messages,
        max_tokens=50,
        temperature=0.5
    )
    assert response == "Raw LLM response"

@pytest.mark.asyncio
async def test_call_llm_structured_success(mock_get_config, mock_async_openai_client, mock_instructor_patch, monkeypatch):
    # Patch AsyncOpenAI where it's used in the llm_client module
    mock_constructor = MagicMock(return_value=mock_async_openai_client)
    monkeypatch.setattr("ciris_engine.services.llm_client.AsyncOpenAI", mock_constructor)

    client = CIRISLLMClient()

    # Mock the response from the instructor-patched client
    expected_response_model = MockResponseModel(message="Structured data", value=123)
    # The patched client's create method is what instructor uses
    mock_instructor_patch.return_value.chat.completions.create.return_value = expected_response_model
    
    messages = [{"role": "user", "content": "Get structured data"}]
    response = await client.call_llm_structured(
        messages=messages,
        response_model=MockResponseModel,
        max_tokens=60,
        temperature=0.1
    )
    
    mock_instructor_patch.return_value.chat.completions.create.assert_awaited_once_with(
        model=client.model_name,
        messages=messages,
        response_model=MockResponseModel,
        max_retries=client.config.max_retries,
        max_tokens=60,
        temperature=0.1
    )
    assert response == expected_response_model
    assert response.message == "Structured data"
    assert response.value == 123

@pytest.mark.parametrize("raw_input, expected_output", [
    ("```json\n{\"key\": \"value\"}\n```", {"key": "value"}),
    ("Some text ```{\"key\": \"value\"}``` more text", {"key": "value"}),
    ("{\"key\": \"value\", \"nested\": {\"num\": 1}}", {"key": "value", "nested": {"num": 1}}),
    ("  {\"key\": \"value with spaces\"}  ", {"key": "value with spaces"}),
    ("Text before {\"key\": \"value\"} text after", {"key": "value"}),
    ("{'key': 'single quotes'}", {"key": "single quotes"}), # Test single quote fix
    ("Malformed JSON", {"error_contains": "Failed to parse JSON"}), # Check for error substring
    ("```\n{\n  \"complex\": true,\n  \"value\": 123\n}\n```", {"complex": True, "value": 123}),
    ("Leading text ```json\n{\n  \"complex\": true,\n  \"value\": 123\n}\n``` Trailing text", {"complex": True, "value": 123}),
])
def test_extract_json(raw_input, expected_output):
    result = CIRISLLMClient.extract_json(raw_input)
    if "error_contains" in expected_output:
        assert "error" in result
        assert expected_output["error_contains"] in result["error"]
    elif "error" in expected_output: # For exact error match if needed later
        assert "error" in result
        assert expected_output["error"] == result["error"]
    else:
        assert result == expected_output

def test_extract_json_non_string_input():
    result = CIRISLLMClient.extract_json(123) # type: ignore
    assert "error" in result
    assert result["error"] == "Invalid input type to extract_json."


def test_llm_client_base_url_propagation(mock_get_config, mock_app_config: AppConfig, mock_async_openai_client, mock_instructor_patch, monkeypatch):
    """Test that the base_url is correctly set on both raw and patched clients."""
    # Patch AsyncOpenAI constructor
    mock_constructor = MagicMock(return_value=mock_async_openai_client)
    monkeypatch.setattr("ciris_engine.services.llm_client.AsyncOpenAI", mock_constructor)

    # Set a specific base_url in the config for this test
    expected_base_url = "http://test-local-llm:8080/v1"
    mock_app_config.llm_services.openai.base_url = expected_base_url
    # Ensure get_config returns this modified config
    monkeypatch.setattr("ciris_engine.services.llm_client.get_config", lambda: mock_app_config)

    # Temporarily remove env vars that could override the mock config's base_url
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    monkeypatch.delenv(mock_app_config.llm_services.openai.api_key_env_var, raising=False)


    # Mock the base_url attribute on the client returned by the constructor
    # This simulates the real AsyncOpenAI client having the base_url set
    mock_async_openai_client.base_url = expected_base_url

    # Mock the instructor.patch to return a client that *also* has the base_url
    # We need to simulate the patched client retaining access to the underlying client's properties
    mock_patched_client = AsyncMock()
    # Simulate instructor storing the original client, which has the base_url
    mock_patched_client.client = mock_async_openai_client
    # Make instructor.patch return this specifically crafted mock
    mock_instructor_patch.return_value = mock_patched_client


    # Initialize the client
    client = CIRISLLMClient()

    # 1. Check if AsyncOpenAI constructor was called with the base_url
    mock_constructor.assert_called()
    assert mock_constructor.call_args.kwargs.get("base_url") == expected_base_url

    # 2. Check the base_url on the raw client instance stored in CIRISLLMClient
    assert hasattr(client.client, "base_url")
    assert client.client.base_url == expected_base_url

    # 3. Check the base_url on the underlying client of the instructor-patched instance
    # Accessing via .client as simulated in our mock_patched_client setup
    assert hasattr(client.instruct_client, "client")
    assert hasattr(client.instruct_client.client, "base_url")
    assert client.instruct_client.client.base_url == expected_base_url
