import pytest
import instructor
import uuid
import json # Added for mocking JSON string response
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from openai import AsyncOpenAI

from ciris_engine.core.agent_processing_queue import ProcessingQueueItem
from ciris_engine.core.dma_results import CSDMAResult
from ciris_engine.core.agent_core_schemas import ThoughtStatus
from ciris_engine.dma.csdma import CSDMAEvaluator
from ciris_engine.core.config_schemas import DEFAULT_OPENAI_MODEL_NAME, AppConfig, OpenAIConfig, LLMServicesConfig # Added imports

# Fixture for a mock instructor client
@pytest.fixture
def mock_openai_client(): # Renamed for clarity, as it's a raw client now
    mock_client = MagicMock(spec=AsyncOpenAI) # Mocking the raw OpenAI client
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock() # This is what instructor will call
    return mock_client

# Fixture for a basic ProcessingQueueItem
@pytest.fixture
def sample_thought_item():
    now_iso = datetime.now(timezone.utc).isoformat()
    return ProcessingQueueItem(
        thought_id=str(uuid.uuid4()),
        source_task_id=str(uuid.uuid4()),
        thought_type="test_thought",
        status=ThoughtStatus.PENDING,
        created_at=now_iso,
        updated_at=now_iso,
        round_created=1,
        priority=5,
        content={"text": "Is it plausible for ice to stay frozen in a hot pan?"},
        processing_context={},
        initial_context={"environment_context": {"description": "Standard Earth physics apply."}}
    )

@pytest.mark.asyncio
class TestCSDMAEvaluator:

    @pytest.fixture
    def csdma_evaluator(self, mock_openai_client: MagicMock, monkeypatch): # Use renamed mock_openai_client
        # Mock get_config for CSDMAEvaluator
        mock_config = AppConfig(llm_services=LLMServicesConfig(openai=OpenAIConfig(instructor_mode="JSON")))
        monkeypatch.setattr("ciris_engine.dma.csdma.get_config", lambda: mock_config)
        evaluator = CSDMAEvaluator(aclient=mock_openai_client, model_name="test-csdma-model")
        # Replace the patched create method with a new AsyncMock
        evaluator.aclient.chat.completions.create = AsyncMock(name="patched_csdma_create_mock")
        return evaluator

    async def test_evaluate_thought_success(self, csdma_evaluator: CSDMAEvaluator, sample_thought_item: ProcessingQueueItem):
        """Test successful evaluation using instructor."""
        # This is the Pydantic object the SUT expects instructor to return
        expected_result_obj = CSDMAResult(
            common_sense_plausibility_score=0.1,
            flags=["Physical_Implausibility_Ignored_Interaction"],
            reasoning="Ice melts rapidly on a hot pan due to heat transfer."
            # raw_llm_response will be set by the SUT based on _raw_response
        )
        
        # This simulates the raw OpenAI API response object
        mock_raw_openai_response = MagicMock(name="raw_openai_response")
        # Attach it to the Pydantic object as instructor would
        expected_result_obj._raw_response = mock_raw_openai_response
        
        # Set the return value of the *mocked patched* create method
        csdma_evaluator.aclient.chat.completions.create.return_value = expected_result_obj
        
        result = await csdma_evaluator.evaluate_thought(sample_thought_item)

        assert isinstance(result, CSDMAResult)
        assert result.common_sense_plausibility_score == expected_result_obj.common_sense_plausibility_score
        assert result.flags == expected_result_obj.flags
        assert result.reasoning == expected_result_obj.reasoning
        assert result.raw_llm_response == str(mock_raw_openai_response) # SUT sets this from _raw_response

        csdma_evaluator.aclient.chat.completions.create.assert_awaited_once()
        call_args = csdma_evaluator.aclient.chat.completions.create.call_args.kwargs
        assert call_args['model'] == csdma_evaluator.model_name
        assert call_args['response_model'] == CSDMAResult
        assert len(call_args['messages']) == 2
        assert call_args['messages'][0]['role'] == 'system' # Use ['key'] access
        assert call_args['messages'][1]['role'] == 'user'
        assert sample_thought_item.content["text"] in call_args['messages'][1]['content']
        assert "Standard Earth physics apply" in call_args['messages'][0]['content']


    async def test_evaluate_thought_instructor_retry_exception(self, csdma_evaluator: CSDMAEvaluator, sample_thought_item: ProcessingQueueItem):
        """Test handling of InstructorRetryException."""
        error_message = "Validation failed"
        mock_exception = instructor.exceptions.InstructorRetryException(
            error_message,
            n_attempts=1,
            total_usage=None
        )
        # If the exception object itself has an 'errors' method that instructor uses:
        # mock_exception.errors = MagicMock(return_value={"detail": "Mock validation error detail"})
        
        csdma_evaluator.aclient.chat.completions.create.side_effect = mock_exception

        result = await csdma_evaluator.evaluate_thought(sample_thought_item)

        assert isinstance(result, CSDMAResult)
        assert result.common_sense_plausibility_score == 0.0
        assert "Instructor_ValidationError" in result.flags
        assert "Failed CSDMA evaluation via instructor due to validation error" in result.reasoning
        assert "InstructorRetryException" in result.raw_llm_response
        assert error_message in result.raw_llm_response # Original error message

        csdma_evaluator.aclient.chat.completions.create.assert_awaited_once()

    async def test_evaluate_thought_generic_exception(self, csdma_evaluator: CSDMAEvaluator, sample_thought_item: ProcessingQueueItem):
        """Test handling of a generic Exception during LLM call."""
        error_message = "Generic LLM API error"
        # Set side_effect on the *mocked patched* create method
        csdma_evaluator.aclient.chat.completions.create.side_effect = Exception(error_message)

        result = await csdma_evaluator.evaluate_thought(sample_thought_item)

        assert isinstance(result, CSDMAResult)
        assert result.common_sense_plausibility_score == 0.0
        assert "LLM_Error_Instructor" in result.flags
        assert f"Failed CSDMA evaluation via instructor: {error_message}" in result.reasoning
        assert f"Exception: {error_message}" in result.raw_llm_response

        csdma_evaluator.aclient.chat.completions.create.assert_awaited_once()

    async def test_context_extraction_from_initial_context(self, csdma_evaluator: CSDMAEvaluator, sample_thought_item: ProcessingQueueItem):
        """Test that context is correctly extracted from initial_context."""
        expected_result_obj = CSDMAResult(common_sense_plausibility_score=0.9, flags=[], reasoning="OK")
        mock_raw_openai_response = MagicMock(name="raw_openai_response_context")
        expected_result_obj._raw_response = mock_raw_openai_response
        csdma_evaluator.aclient.chat.completions.create.return_value = expected_result_obj
        
        sample_thought_item.initial_context = {"environment_context": "A hypothetical world without friction."}
        await csdma_evaluator.evaluate_thought(sample_thought_item)

        csdma_evaluator.aclient.chat.completions.create.assert_awaited_once()
        call_args = csdma_evaluator.aclient.chat.completions.create.call_args.kwargs
        system_message = call_args['messages'][0]['content']
        assert "Context Grounding: The context is: A hypothetical world without friction." in system_message

    async def test_context_extraction_default(self, csdma_evaluator: CSDMAEvaluator, sample_thought_item: ProcessingQueueItem):
        """Test that default context is used when initial_context is missing or malformed."""
        expected_result_obj = CSDMAResult(common_sense_plausibility_score=0.9, flags=[], reasoning="OK")
        mock_raw_openai_response = MagicMock(name="raw_openai_response_default_ctx")
        expected_result_obj._raw_response = mock_raw_openai_response
        csdma_evaluator.aclient.chat.completions.create.return_value = expected_result_obj

        sample_thought_item.initial_context = {} # Empty context
        await csdma_evaluator.evaluate_thought(sample_thought_item)

        csdma_evaluator.aclient.chat.completions.create.assert_awaited_once()
        call_args = csdma_evaluator.aclient.chat.completions.create.call_args.kwargs
        system_message = call_args['messages'][0]['content']
        assert "Context Grounding: The context is: Standard Earth-based physical context, unless otherwise specified in the thought." in system_message

    async def test_content_extraction_from_processing_queue_item(self, csdma_evaluator: CSDMAEvaluator, sample_thought_item: ProcessingQueueItem):
        """Test different ways content string is extracted."""
        expected_result_obj = CSDMAResult(common_sense_plausibility_score=0.9, flags=[], reasoning="OK")
        mock_raw_openai_response = MagicMock(name="raw_openai_response_content_extract")
        expected_result_obj._raw_response = mock_raw_openai_response
        csdma_evaluator.aclient.chat.completions.create.return_value = expected_result_obj

        # 1. Test with 'text' key
        sample_thought_item.content = {"text": "Content from text key"}
        await csdma_evaluator.evaluate_thought(sample_thought_item)
        call_args = csdma_evaluator.aclient.chat.completions.create.call_args.kwargs
        user_message = call_args['messages'][1]['content']
        assert 'Content from text key' in user_message
        csdma_evaluator.aclient.chat.completions.create.assert_awaited_once() # Check call happened

        # 2. Test with 'description' key (fallback)
        csdma_evaluator.aclient.chat.completions.create.reset_mock()
        sample_thought_item.content = {"description": "Content from description key"}
        await csdma_evaluator.evaluate_thought(sample_thought_item)
        call_args = csdma_evaluator.aclient.chat.completions.create.call_args.kwargs
        user_message = call_args['messages'][1]['content']
        assert 'Content from description key' in user_message
        csdma_evaluator.aclient.chat.completions.create.assert_awaited_once()

        # 3. Test with other dict structure (fallback to str())
        csdma_evaluator.aclient.chat.completions.create.reset_mock()
        sample_thought_item.content = {"other": "value", "another": 123}
        await csdma_evaluator.evaluate_thought(sample_thought_item)
        call_args = csdma_evaluator.aclient.chat.completions.create.call_args.kwargs
        user_message = call_args['messages'][1]['content']
        assert str({"other": "value", "another": 123}) in user_message
        csdma_evaluator.aclient.chat.completions.create.assert_awaited_once()
        
    def test_repr_method(self, csdma_evaluator: CSDMAEvaluator):
        """Test the __repr__ method."""
        representation = repr(csdma_evaluator)
        assert representation == f"<CSDMAEvaluator model='{csdma_evaluator.model_name}' (using instructor)>"
