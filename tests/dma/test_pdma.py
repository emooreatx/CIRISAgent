import pytest
import json # Added for mocking JSON string response
from unittest.mock import AsyncMock, MagicMock, call
import asyncio

# Module to test
from ciris_engine.dma.pdma import EthicalPDMAEvaluator, DEFAULT_OPENAI_MODEL_NAME
from ciris_engine.schemas.agent_core_schemas_v1 import EthicalPDMAResult
from ciris_engine.agent_processing_queue import ProcessingQueueItem
import instructor # For type hinting the mock
from openai import AsyncOpenAI # For mock_openai_client fixture
# Added imports for mocking OpenAI response structure
import openai.types.chat
from openai.types.chat.chat_completion import ChatCompletion, ChatCompletionMessage, Choice # Corrected import path
from ciris_engine.schemas.config_schemas_v1 import AppConfig, OpenAIConfig, LLMServicesConfig # Added imports

# --- Fixtures ---

@pytest.fixture
def mock_openai_client(): # Renamed for clarity
    """Mocks an AsyncOpenAI client."""
    mock_client = MagicMock(spec=AsyncOpenAI) # Mocking the raw OpenAI client
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock() # This is what instructor will call
    return mock_client # Return the raw mock client

@pytest.fixture
def pdma_evaluator(mock_openai_client, monkeypatch): # Use the raw mock_openai_client
    """
    Provides an EthicalPDMAEvaluator instance.
    The internal patched client's create method is replaced with an AsyncMock.
    """
    # Mock config if needed by __init__
    mock_config = AppConfig(llm_services=LLMServicesConfig(openai=OpenAIConfig(instructor_mode="JSON", model_name="default-model-from-config")))
    monkeypatch.setattr("ciris_engine.config.config_manager.get_config", lambda: mock_config)

    # Initialize the evaluator - this will patch the mock_openai_client internally
    evaluator = EthicalPDMAEvaluator(aclient=mock_openai_client, model_name="test-pdma-model")

    # IMPORTANT: Replace the *patched* create method with a new AsyncMock for testing
    # This allows us to control what the evaluator receives from the instructor-patched call
    evaluator.aclient.chat.completions.create = AsyncMock(name="patched_create_mock")
    return evaluator

@pytest.fixture
def sample_thought_item():
    """Provides a sample ProcessingQueueItem for testing."""
    return ProcessingQueueItem(
        thought_id="pdma-test-thought-1",
        source_task_id="pdma-test-task-1",
        content="User asks: Is it okay to lie to protect someone's feelings?",
        priority=1,
        thought_type="ethical_query"
        # Add other necessary fields if ProcessingQueueItem schema changes
    )

# --- Helper Class for Mocking ---

class MockChatCompletionResponse:
    """A simple class to mimic openai.types.chat.ChatCompletion for instructor parsing."""
    def __init__(self, content_json_string: str, model_name: str):
        class MockMessage:
            def __init__(self, content_str):
                self.content = content_str
                self.tool_calls = None  # Explicitly None
                self.function_call = None # Explicitly None

            def model_dump(self): # Add model_dump if instructor's dump_message calls it
                return {
                    "content": self.content,
                    "tool_calls": self.tool_calls,
                    "function_call": self.function_call,
                    # Add other fields if necessary, e.g., 'role': 'assistant'
                }

        class MockChoice:
            def __init__(self, message_obj):
                self.message = message_obj
                self.finish_reason = "stop" # Common value
        self.choices = [MockChoice(MockMessage(content_json_string))]
        # Include other attributes instructor might access or attach to _raw_response
        self.id = "chatcmpl-mock-id"
        self.model = model_name
        self.object = "chat.completion"
        self.created = 1234567890
        self.usage = None # Or mock openai.types.CompletionUsage if needed

    def __str__(self):
        # Provide a basic string representation for the raw_llm_response assertion
        return f"MockChatCompletionResponse(id={self.id}, model={self.model})"

# --- Test Cases ---

@pytest.mark.asyncio
async def test_pdma_evaluate_success(pdma_evaluator: EthicalPDMAEvaluator, sample_thought_item: ProcessingQueueItem): # Removed mock_openai_client dependency here
    """Test successful evaluation returning a valid EthicalPDMAResult."""
    # Define the expected structured response (using aliases)
    expected_result_data = {
        "Context": "User asks about lying to protect feelings. Stakeholders: user, person lied to. Constraints: honesty, potential harm.",
        "Alignment-Check": {
            "plausible_actions": ["Lie", "Tell truth gently", "Avoid answering"],
            "do_good": "Potentially avoids immediate hurt (Lie) vs. promotes understanding (Truth).",
            "avoid_harm": "Lying causes harm through deception vs. truth might cause emotional harm.",
            "honor_autonomy": "Lying disrespects autonomy vs. truth respects it.",
            "ensure_fairness": "Treating the person lied to unfairly.",
            "fidelity_transparency": "Lying violates transparency.",
            "integrity": "Lying compromises integrity.",
            "meta_goal_m1": "Consistent application of principles needed."
        },
        "Conflicts": "Do Good (avoid immediate hurt) vs. Avoid Harm (deception), Honor Autonomy, Fidelity/Transparency, Integrity.",
        "Resolution": "Prioritize Avoid Harm (long-term deception) and Autonomy. Gentle truth or avoidance preferred over lying.",
        "Decision": "Recommend avoiding the lie. Opt for a gentle, partial truth or deflecting the question if full truth is too harmful, while acknowledging the ethical conflict.",
        "Monitoring": {"metric_to_watch": "User reaction, relationship impact", "update_trigger": "If user pushes for a direct lie or negative outcome observed."}
    }
    # Instantiate the expected Pydantic model
    expected_result_obj = EthicalPDMAResult.model_validate(expected_result_data)
    expected_json_content = expected_result_obj.model_dump_json() # Still useful for creating mock raw response

    # Create a mock raw response object (using the helper class)
    # This simulates what instructor would attach to _raw_response
    mock_raw_response = MockChatCompletionResponse(
        content_json_string=expected_json_content,
        model_name=pdma_evaluator.model_name
    )

    # Simulate instructor attaching the raw response to the Pydantic object
    expected_result_obj._raw_response = mock_raw_response

    # Set the return value of the *mocked patched* create method
    # This is what the evaluator's `evaluate` method will receive
    pdma_evaluator.aclient.chat.completions.create.return_value = expected_result_obj

    # Call the evaluate method
    actual_result = await pdma_evaluator.evaluate(sample_thought_item)

    # Assertions
    assert isinstance(actual_result, EthicalPDMAResult)
    # Compare Pydantic models directly (handles field comparison)
    assert actual_result == expected_result_obj
    # Explicitly check the raw_llm_response field set by the SUT
    assert actual_result.raw_llm_response == str(mock_raw_response)


    # Verify the *mocked patched* create method was called correctly
    pdma_evaluator.aclient.chat.completions.create.assert_awaited_once()
    call_args = pdma_evaluator.aclient.chat.completions.create.call_args.kwargs
    # Check arguments passed to the patched create method
    assert call_args['model'] == pdma_evaluator.model_name
    assert call_args['response_model'] == EthicalPDMAResult
    assert call_args['messages'][0]['role'] == 'system'
    assert "PDMA" in call_args['messages'][0]['content']
    assert call_args['messages'][1]['role'] == 'user'
    assert sample_thought_item.content in call_args['messages'][1]['content']

@pytest.mark.asyncio
async def test_pdma_evaluate_llm_error(pdma_evaluator: EthicalPDMAEvaluator, sample_thought_item: ProcessingQueueItem): # Removed mock_openai_client
    """Test evaluation when the underlying LLM call fails."""
    error_message = "LLM Unavailable"
    # Set side_effect on the *mocked patched* create method
    pdma_evaluator.aclient.chat.completions.create.side_effect = Exception(error_message)

    # Call the evaluate method
    actual_result = await pdma_evaluator.evaluate(sample_thought_item)

    # Assertions for fallback object
    assert isinstance(actual_result, EthicalPDMAResult)
    assert "Error: LLM call via instructor failed" in actual_result.context
    # Check that the original error message is captured in the fallback object
    assert "error" in actual_result.alignment_check
    assert error_message in actual_result.alignment_check["error"]
    assert "Error: LLM/Instructor error" in actual_result.decision
    assert "error" in actual_result.monitoring
    assert error_message in actual_result.monitoring["error"]
    assert actual_result.conflicts is None # Optional field defaults to None
    assert actual_result.resolution is None # Optional field defaults to None
    assert f"Exception during evaluation: {error_message}" in actual_result.raw_llm_response
    assert "LLM Unavailable" in actual_result.raw_llm_response # Ensure original error is in raw_llm_response

    # Verify the *mocked patched* create method was called
    pdma_evaluator.aclient.chat.completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_pdma_uses_default_model(mock_openai_client: MagicMock, sample_thought_item: ProcessingQueueItem, monkeypatch): # Keep mock_openai_client for init
    """Test that the default model is used if none is provided during init."""
    # Mock get_config for default model name
    mock_config = AppConfig(llm_services=LLMServicesConfig(openai=OpenAIConfig(model_name=DEFAULT_OPENAI_MODEL_NAME, instructor_mode="JSON")))
    monkeypatch.setattr("ciris_engine.config.config_manager.get_config", lambda: mock_config)

    # Create evaluator without specifying model_name - it patches mock_openai_client
    default_evaluator = EthicalPDMAEvaluator(aclient=mock_openai_client)
    assert default_evaluator.model_name == DEFAULT_OPENAI_MODEL_NAME

    # Replace the *patched* create method AFTER init
    default_evaluator.aclient.chat.completions.create = AsyncMock(name="patched_create_mock_default")

    # Configure mock return value (Pydantic object + raw response)
    llm_produced_data_obj = EthicalPDMAResult(
        context="Default context", # Use lowercase field name
        alignment_check={"default": "check"},
        Decision="Default decision",
        Monitoring="Default monitoring"
    )
    expected_json_content = llm_produced_data_obj.model_dump_json()

    # Create mock raw response
    mock_raw_response_default = MockChatCompletionResponse(
        content_json_string=expected_json_content,
        model_name=DEFAULT_OPENAI_MODEL_NAME
    )
    # Attach raw response
    llm_produced_data_obj._raw_response = mock_raw_response_default

    # Set the return value of the *mocked patched* create method
    default_evaluator.aclient.chat.completions.create.return_value = llm_produced_data_obj

    # Call evaluate
    actual_result = await default_evaluator.evaluate(sample_thought_item)

    # Basic check that we got a result back
    assert isinstance(actual_result, EthicalPDMAResult)
    assert actual_result.context == "Default context"

    # Verify the *mocked patched* create method was called with the default model
    default_evaluator.aclient.chat.completions.create.assert_awaited_once()
    call_args = default_evaluator.aclient.chat.completions.create.call_args.kwargs
    assert call_args['model'] == DEFAULT_OPENAI_MODEL_NAME

def test_pdma_evaluator_repr(pdma_evaluator: EthicalPDMAEvaluator):
    """Test the __repr__ method."""
    representation = repr(pdma_evaluator)
    assert isinstance(representation, str)
    assert pdma_evaluator.model_name in representation
    assert "EthicalPDMAEvaluator" in representation
    assert "instructor" in representation
