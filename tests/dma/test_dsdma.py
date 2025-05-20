import pytest
import instructor
import uuid
import json # Added for mocking JSON string response
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from openai import AsyncOpenAI
from instructor.exceptions import InstructorRetryException

from ciris_engine.core.agent_processing_queue import ProcessingQueueItem
from ciris_engine.core.dma_results import DSDMAResult
from ciris_engine.core.agent_core_schemas import ThoughtStatus
from ciris_engine.dma.dsdma_teacher import BasicTeacherDSDMA, LLMOutputForDSDMA as TeacherLLMOutput
from ciris_engine.dma.dsdma_student import StudentDSDMA, LLMOutputForDSDMA as StudentLLMOutput
from ciris_engine.core.config_schemas import DEFAULT_OPENAI_MODEL_NAME, AppConfig, OpenAIConfig, LLMServicesConfig # Added missing config imports here


# --- Fixtures ---

@pytest.fixture
def mock_openai_client():
    """Mocks a raw AsyncOpenAI client."""
    mock_client = MagicMock(spec=AsyncOpenAI)
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock() # This is the method instructor patches/calls
    return mock_client

@pytest.fixture
def mock_instructor_client():
    """Mocks an instructor-patched AsyncOpenAI client."""
    mock_client = MagicMock(spec=instructor.Instructor)
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock()
    return mock_client

@pytest.fixture
def sample_thought_item():
    """Provides a sample ProcessingQueueItem for testing."""
    now_iso = datetime.now(timezone.utc).isoformat()
    return ProcessingQueueItem(
        thought_id=str(uuid.uuid4()),
        source_task_id=str(uuid.uuid4()),
        thought_type="test_dsdma_thought",
        status=ThoughtStatus.PENDING,
        created_at=now_iso,
        updated_at=now_iso,
        round_created=1,
        priority=5,
        content={"text": "Should we discuss advanced quantum physics in the #general channel?"},
        processing_context={},
        initial_context={"channel_name": "#general", "user_id": "user123"} # Example context
    )

# --- Test Class for BasicTeacherDSDMA ---

@pytest.mark.asyncio
class TestBasicTeacherDSDMA:

    @pytest.fixture
    def teacher_dsdma(self, mock_openai_client: MagicMock, monkeypatch):
        """Provides a BasicTeacherDSDMA instance."""
        mock_config = AppConfig(llm_services=LLMServicesConfig(openai=OpenAIConfig(instructor_mode="JSON")))
        monkeypatch.setattr("ciris_engine.dma.dsdma_base.get_config", lambda: mock_config)
        evaluator = BasicTeacherDSDMA(
            aclient=mock_openai_client, # Pass raw OpenAI client
            model_name="test-teacher-model",
            domain_specific_knowledge={"rules_summary": "Keep discussions relevant to the channel topic."}
        )
        # Replace the patched create method with a new AsyncMock
        evaluator.aclient.chat.completions.create = AsyncMock(name="patched_teacher_dsdma_create_mock")
        return evaluator

    async def test_teacher_evaluate_success(self, teacher_dsdma: BasicTeacherDSDMA, sample_thought_item: ProcessingQueueItem):
        """Test successful evaluation by Teacher DSDMA."""
        # This is the Pydantic object the SUT expects instructor to return
        expected_llm_output = TeacherLLMOutput(
            domain_alignment_score=0.3, # Low score for off-topic
            recommended_action="Suggest moving to #science channel",
            flags=["OffTopic"],
            reasoning="Discussion is too advanced for #general, suggest moving."
        )
        
        # This simulates the raw OpenAI API response object
        mock_raw_openai_response = MagicMock(name="raw_teacher_openai_response")
        # Attach it to the Pydantic object as instructor would
        expected_llm_output._raw_response = mock_raw_openai_response
        
        # Set the return value of the *mocked patched* create method
        teacher_dsdma.aclient.chat.completions.create.return_value = expected_llm_output

        result = await teacher_dsdma.evaluate_thought(sample_thought_item, sample_thought_item.initial_context)

        assert isinstance(result, DSDMAResult)
        assert result.domain_alignment_score == expected_llm_output.domain_alignment_score
        assert result.flags == expected_llm_output.flags
        assert result.reasoning == expected_llm_output.reasoning
        assert result.recommended_action == expected_llm_output.recommended_action
        assert result.raw_llm_response == str(mock_raw_openai_response)

        teacher_dsdma.aclient.chat.completions.create.assert_awaited_once()
        call_args = teacher_dsdma.aclient.chat.completions.create.call_args.kwargs
        assert call_args['model'] == teacher_dsdma.model_name
        assert call_args['response_model'] == TeacherLLMOutput # Internal model used by DSDMA
        assert "Basic Homeroom Teacher" in call_args['messages'][0]['content']
        assert "Keep discussions relevant" in call_args['messages'][0]['content'] # Check domain knowledge in prompt
        assert str(sample_thought_item.initial_context) in call_args['messages'][0]['content'] # Check context in prompt
        assert sample_thought_item.content["text"] in call_args['messages'][1]['content']

    async def test_teacher_evaluate_instructor_error(self, teacher_dsdma: BasicTeacherDSDMA, sample_thought_item: ProcessingQueueItem):
        """Test Teacher DSDMA handling InstructorRetryException."""
        error_message = "Teacher validation failed"
        mock_exception = InstructorRetryException(error_message, n_attempts=1, total_usage=None)
        teacher_dsdma.aclient.chat.completions.create.side_effect = mock_exception

        result = await teacher_dsdma.evaluate_thought(sample_thought_item, sample_thought_item.initial_context)

        assert isinstance(result, DSDMAResult)
        assert result.domain_alignment_score == 0.0
        assert "Instructor_ValidationError" in result.flags
        assert "Failed DSDMA evaluation via instructor due to validation error" in result.reasoning
        assert error_message in result.raw_llm_response
        assert "InstructorRetryException" in result.raw_llm_response
        teacher_dsdma.aclient.chat.completions.create.assert_awaited_once()

    async def test_teacher_evaluate_generic_error(self, teacher_dsdma: BasicTeacherDSDMA, sample_thought_item: ProcessingQueueItem):
        """Test Teacher DSDMA handling generic Exception."""
        error_message = "Teacher generic API error"
        teacher_dsdma.aclient.chat.completions.create.side_effect = Exception(error_message)

        result = await teacher_dsdma.evaluate_thought(sample_thought_item, sample_thought_item.initial_context)

        assert isinstance(result, DSDMAResult)
        assert result.domain_alignment_score == 0.0
        assert "LLM_Error_Instructor" in result.flags
        assert f"Failed DSDMA evaluation via instructor: {error_message}" in result.reasoning
        assert f"Exception: {error_message}" in result.raw_llm_response
        teacher_dsdma.aclient.chat.completions.create.assert_awaited_once()

    def test_teacher_repr(self, teacher_dsdma: BasicTeacherDSDMA):
        """Test Teacher DSDMA __repr__."""
        assert repr(teacher_dsdma) == f"<BasicTeacherDSDMA model='{teacher_dsdma.model_name}' (using instructor)>"


# --- Test Class for StudentDSDMA ---

@pytest.mark.asyncio
class TestStudentDSDMA:

    @pytest.fixture
    def student_dsdma(self, mock_openai_client: MagicMock, monkeypatch):
        """Provides a StudentDSDMA instance."""
        mock_config = AppConfig(llm_services=LLMServicesConfig(openai=OpenAIConfig(instructor_mode="JSON")))
        monkeypatch.setattr("ciris_engine.dma.dsdma_base.get_config", lambda: mock_config)
        evaluator = StudentDSDMA(
            aclient=mock_openai_client, # Pass raw OpenAI client
            model_name="test-student-model",
            domain_specific_knowledge={"rules_summary": "General discussion"}
        )
        # Replace the patched create method with a new AsyncMock
        evaluator.aclient.chat.completions.create = AsyncMock(name="patched_student_dsdma_create_mock")
        return evaluator

    async def test_student_evaluate_success(self, student_dsdma: StudentDSDMA, sample_thought_item: ProcessingQueueItem):
        """Test successful evaluation by Student DSDMA."""
        expected_llm_output = StudentLLMOutput(
            domain_alignment_score=0.9, # High score for learning opportunity
            recommended_action="Ask clarifying questions about quantum physics",
            flags=["LearningOpportunity"],
            reasoning="Topic is complex and offers a chance to learn, engage curiously."
        )
        
        mock_raw_openai_response = MagicMock(name="raw_student_openai_response")
        expected_llm_output._raw_response = mock_raw_openai_response
        
        student_dsdma.aclient.chat.completions.create.return_value = expected_llm_output

        result = await student_dsdma.evaluate_thought(sample_thought_item, sample_thought_item.initial_context)

        assert isinstance(result, DSDMAResult)
        assert result.domain_alignment_score == expected_llm_output.domain_alignment_score
        assert result.flags == expected_llm_output.flags
        assert result.reasoning == expected_llm_output.reasoning
        assert result.recommended_action == expected_llm_output.recommended_action
        assert result.raw_llm_response == str(mock_raw_openai_response)

        student_dsdma.aclient.chat.completions.create.assert_awaited_once()
        call_args = student_dsdma.aclient.chat.completions.create.call_args.kwargs
        assert call_args['model'] == student_dsdma.model_name
        assert call_args['response_model'] == StudentLLMOutput # Internal model used by DSDMA
        assert "curious learner DSDMA" in call_args['messages'][0]['content']
        assert "General discussion" in call_args['messages'][0]['content'] # Check domain knowledge
        assert str(sample_thought_item.initial_context) in call_args['messages'][0]['content'] # Check context
        assert sample_thought_item.content["text"] in call_args['messages'][1]['content']

    async def test_student_evaluate_instructor_error(self, student_dsdma: StudentDSDMA, sample_thought_item: ProcessingQueueItem):
        """Test Student DSDMA handling InstructorRetryException."""
        error_message = "Student validation failed"
        mock_exception = InstructorRetryException(error_message, n_attempts=1, total_usage=None)
        student_dsdma.aclient.chat.completions.create.side_effect = mock_exception

        result = await student_dsdma.evaluate_thought(sample_thought_item, sample_thought_item.initial_context)

        assert isinstance(result, DSDMAResult)
        assert result.domain_alignment_score == 0.0
        assert "Instructor_ValidationError" in result.flags
        assert "Failed DSDMA evaluation via instructor due to validation error" in result.reasoning
        assert error_message in result.raw_llm_response
        assert "InstructorRetryException" in result.raw_llm_response
        student_dsdma.aclient.chat.completions.create.assert_awaited_once()

    async def test_student_evaluate_generic_error(self, student_dsdma: StudentDSDMA, sample_thought_item: ProcessingQueueItem):
        """Test Student DSDMA handling generic Exception."""
        error_message = "Student generic API error"
        student_dsdma.aclient.chat.completions.create.side_effect = Exception(error_message)

        result = await student_dsdma.evaluate_thought(sample_thought_item, sample_thought_item.initial_context)

        assert isinstance(result, DSDMAResult)
        assert result.domain_alignment_score == 0.0
        assert "LLM_Error_Instructor" in result.flags
        assert f"Failed DSDMA evaluation via instructor: {error_message}" in result.reasoning
        assert f"Exception: {error_message}" in result.raw_llm_response
        student_dsdma.aclient.chat.completions.create.assert_awaited_once()

    def test_student_repr(self, student_dsdma: StudentDSDMA):
        """Test Student DSDMA __repr__."""
        assert repr(student_dsdma) == f"<StudentDSDMA model='{student_dsdma.model_name}' (using instructor)>"
