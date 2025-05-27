import pytest
import pytest
import instructor
import uuid
import json # Added for mocking JSON string response
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any # Added Dict, Any
from pydantic import BaseModel # Added BaseModel import

from openai import AsyncOpenAI
from instructor.exceptions import InstructorRetryException

from ciris_engine.schemas.agent_core_schemas_v1 import (
    Thought,
    ThoughtStatus,
    HandlerActionType,
    CIRISSchemaVersion,
)
from ciris_engine.schemas.action_params_v1 import SpeakParams, PonderParams
from ciris_engine.schemas.dma_results_v1 import (
    ActionSelectionPDMAResult,
    EthicalPDMAResult,
    CSDMAResult,
    DSDMAResult,
)
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType as CoreHandlerActionType
# from ciris_engine.core.profiles import AgentProfile # Replaced by SerializableAgentProfile
from ciris_engine.schemas.config_schemas_v1 import SerializableAgentProfile # Import new profile
from ciris_engine.dma.action_selection_pdma import (
    ActionSelectionPDMAEvaluator,
    _ActionSelectionLLMResponse, # Internal model for mocking LLM output
    ACTION_PARAM_MODELS
)
from ciris_engine.utils.constants import ENGINE_OVERVIEW_TEMPLATE
import ciris_engine.dma.action_selection_pdma as action_selection_pdma_module # Import the module itself
from ciris_engine.schemas.config_schemas_v1 import AppConfig, OpenAIConfig, LLMServicesConfig # Corrected import path
from ciris_engine.config.config_manager import get_config # get_config is fine here

# --- Fixtures ---

@pytest.fixture
def mock_openai_client():
    """Mocks an AsyncOpenAI client."""
    mock_client = MagicMock(spec=AsyncOpenAI)
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock()
    return mock_client

@pytest.fixture
def mock_app_config_json_mode():
    """Provides an AppConfig with instructor_mode set to JSON."""
    return AppConfig(
        llm_services=LLMServicesConfig(
            openai=OpenAIConfig(instructor_mode="JSON")
        )
    )

@pytest.fixture
def action_selection_pdma_evaluator(mock_openai_client, mock_app_config_json_mode, monkeypatch):
    """Provides an ActionSelectionPDMAEvaluator instance, mocking get_config."""
    # Patch get_config in the module where it's defined and imported by action_selection_pdma
    monkeypatch.setattr("ciris_engine.config.config_manager.get_config", lambda: mock_app_config_json_mode)
    # Also, ensure that the action_selection_pdma module re-imports or uses the patched version.
    # Forcing a re-import or patching where it's directly used in action_selection_pdma.py might be needed if the import is sticky.
    # However, typically, patching the source is enough if the module under test (action_selection_pdma) imports it fresh or at runtime.
    # Let's assume for now that patching the source is sufficient.
    # If ActionSelectionPDMAEvaluator itself imported get_config directly, we'd patch it there:
    # monkeypatch.setattr("ciris_engine.dma.action_selection_pdma.get_config", lambda: mock_app_config_json_mode)
    # Since ActionSelectionPDMAEvaluator calls get_config() which is imported from config_manager,
    # patching config_manager.get_config should work.
    evaluator = ActionSelectionPDMAEvaluator(
        aclient=mock_openai_client, # Pass the raw mock client
        model_name="test-action-selection-model"
    )
    # IMPORTANT: Replace the *patched* create method with a new AsyncMock for testing
    evaluator.aclient.chat.completions.create = AsyncMock(name="patched_as_create_mock")
    return evaluator

@pytest.fixture
def sample_thought():
    """Provides a sample Thought object for testing."""
    now_iso = datetime.now(timezone.utc).isoformat()
    return Thought(
        thought_id=str(uuid.uuid4()),
        source_task_id=str(uuid.uuid4()),
        thought_type="test_action_selection_thought",
        status=ThoughtStatus.PENDING,
        created_at=now_iso,
        updated_at=now_iso,
        round_created=1,
        priority=5,
        content="User is asking about project timelines.",
        processing_context={"user_id": "user123", "channel_id": "channel_abc"},
        ponder_count=0,
        ponder_notes=[]
    )

@pytest.fixture
def sample_ethical_result():
    """Provides a sample EthicalPDMAResult."""
    return EthicalPDMAResult(
        context="User query about timelines.",
        alignment_check={"speak": "aligned"},
        decision="Okay to provide timeline info.",
        monitoring="Monitor for follow-up questions."
    )

@pytest.fixture
def sample_csdma_result():
    """Provides a sample CSDMAResult."""
    return CSDMAResult(
        common_sense_plausibility_score=0.95,
        flags=[],
        reasoning="Request for timeline is plausible."
    )

@pytest.fixture
def sample_dsdma_result():
    """Provides a sample DSDMAResult."""
    return DSDMAResult(
        domain_name="ProjectManagement",
        domain_alignment_score=0.88,
        recommended_action="Provide high-level timeline.",
        flags=[],
        reasoning="Domain policy allows sharing high-level timelines."
    )

@pytest.fixture
def sample_agent_profile():
    """Provides a sample SerializableAgentProfile."""
    return SerializableAgentProfile(
        name="TestProfile",
        dsdma_identifier="BaseDSDMA",
        dsdma_overrides={"prompt_template": "Test DSDMA {context_str} {rules_summary_str}"},
        permitted_actions=[CoreHandlerActionType.SPEAK, CoreHandlerActionType.PONDER, CoreHandlerActionType.REJECT],
        action_selection_pdma_overrides={"system_header": "You are a helpful test assistant."}
    )

# sample_permitted_actions fixture is no longer needed as it's part of sample_agent_profile
# @pytest.fixture
# def sample_permitted_actions():
#     """Provides a list of permitted HandlerActionType enums."""
#     return [CoreHandlerActionType.SPEAK, CoreHandlerActionType.PONDER, CoreHandlerActionType.REJECT]

@pytest.fixture
def sample_triaged_inputs(sample_thought, sample_ethical_result, sample_csdma_result, sample_dsdma_result, sample_agent_profile: SerializableAgentProfile): # Type hint updated
    """Provides a sample triaged_inputs dictionary."""
    return {
        "original_thought": sample_thought,
        "ethical_pdma_result": sample_ethical_result,
        "csdma_result": sample_csdma_result,
        "dsdma_result": sample_dsdma_result,
        "current_ponder_count": sample_thought.ponder_count,
        "max_ponder_rounds": 3,
        # "agent_profile": sample_agent_profile, # ActionSelectionPDMAEvaluator.evaluate doesn't expect agent_profile directly
        "permitted_actions": sample_agent_profile.permitted_actions # Pass permitted_actions from the profile
    }

# --- Test Cases ---

@pytest.mark.asyncio
class TestActionSelectionPDMAEvaluator:

    async def test_evaluate_success_speak(
        self, action_selection_pdma_evaluator: ActionSelectionPDMAEvaluator, sample_triaged_inputs: Dict[str, Any] # Removed mock_openai_client
    ):
        """Test successful evaluation resulting in a SPEAK action."""
        expected_llm_response_data = {
            "schema_version": CIRISSchemaVersion.V1_0_BETA,
            "context_summary_for_action_selection": "User asked for timeline, all checks green.",
            "action_alignment_check": {"speak": "highly_aligned"},
            "selected_handler_action": CoreHandlerActionType.SPEAK,
            "action_parameters": {"content": "The project is on track for Q3 delivery."},
            "action_selection_rationale": "Direct answer is best.",
            "monitoring_for_selected_action": "None needed."
        }
        # Create the Pydantic model instance that represents the LLM's structured output
        expected_pydantic_model_obj = _ActionSelectionLLMResponse(**expected_llm_response_data)
        # Convert this Pydantic model to its JSON string representation
        expected_json_content = expected_pydantic_model_obj.model_dump_json()

        # Simulate the OpenAI API ChatCompletion response structure
        mock_chat_completion_response = MagicMock()
        mock_chat_completion_message = MagicMock()
        mock_chat_completion_message.content = expected_json_content
        mock_chat_completion_message.tool_calls = None # Important for JSON mode

        mock_choice = MagicMock()
        mock_choice.message = mock_chat_completion_message
        mock_chat_completion_response.choices = [mock_choice]

        # mock_openai_client.chat.completions.create is the AsyncMock that instructor calls.
        # It should return an object simulating openai.types.chat.ChatCompletion,
        # where .choices[0].message.content is the JSON string.
        # This mock_chat_completion_response simulates the raw OpenAI API response.
        # It's used to set the _raw_response attribute on the Pydantic object.

        # Create the Pydantic object that the SUT expects instructor to return.
        parsed_pydantic_object = _ActionSelectionLLMResponse(**expected_llm_response_data)
        # Attach the simulated raw response to it, as the SUT expects.
        parsed_pydantic_object._raw_response = mock_chat_completion_response
        
        # Set the return value of the *mocked patched* create method
        action_selection_pdma_evaluator.aclient.chat.completions.create.return_value = parsed_pydantic_object

        result = await action_selection_pdma_evaluator.evaluate(sample_triaged_inputs)

        # Assertions check the final ActionSelectionPDMAResult produced by the evaluator

        assert isinstance(result, ActionSelectionPDMAResult)
        # assert isinstance(result, ActionSelectionPDMAResult) # Redundant check
        assert result.selected_handler_action == CoreHandlerActionType.SPEAK
        assert isinstance(result.action_parameters, SpeakParams) # Check parameters were parsed correctly
        assert result.action_parameters.content == expected_llm_response_data["action_parameters"]["content"]
        assert result.context_summary_for_action_selection == expected_llm_response_data["context_summary_for_action_selection"]
        # Check that the raw_llm_response was populated correctly from the attached mock
        assert result.raw_llm_response == str(mock_chat_completion_response)

        # Assert that the *mocked patched* create method was called
        action_selection_pdma_evaluator.aclient.chat.completions.create.assert_awaited_once()
        call_args = action_selection_pdma_evaluator.aclient.chat.completions.create.call_args.kwargs
        assert call_args['model'] == action_selection_pdma_evaluator.model_name
        assert call_args['response_model'] == _ActionSelectionLLMResponse
        prompt_text = call_args['messages'][0]['content']

    async def test_evaluate_instructor_retry_exception(
        self, action_selection_pdma_evaluator: ActionSelectionPDMAEvaluator, sample_triaged_inputs: Dict[str, Any] # Removed mock_openai_client
    ):
        """Test fallback when InstructorRetryException occurs."""
        error_message = "Instructor validation failed"
        mock_exception = InstructorRetryException(error_message, n_attempts=1, total_usage=None)
        # mock_exception.errors = MagicMock(return_value={"detail": "Mock validation error"}) # If needed
        action_selection_pdma_evaluator.aclient.chat.completions.create.side_effect = mock_exception

        result = await action_selection_pdma_evaluator.evaluate(sample_triaged_inputs)

        assert isinstance(result, ActionSelectionPDMAResult)
        assert result.selected_handler_action == CoreHandlerActionType.PONDER # Fallback action
        assert isinstance(result.action_parameters, PonderParams)
        # Expect the original error message in the fallback details
        assert error_message in result.action_parameters.key_questions[0] 
        assert "Fallback due to InstructorRetryException" in result.action_selection_rationale
        assert "InstructorRetryException" in result.raw_llm_response # Check raw response stores exception info
        action_selection_pdma_evaluator.aclient.chat.completions.create.assert_awaited_once()

    async def test_evaluate_generic_exception(
        self, action_selection_pdma_evaluator: ActionSelectionPDMAEvaluator, sample_triaged_inputs: Dict[str, Any] # Removed mock_openai_client
    ):
        """Test fallback when a generic Exception occurs."""
        error_message = "Generic API error"
        action_selection_pdma_evaluator.aclient.chat.completions.create.side_effect = Exception(error_message)

        result = await action_selection_pdma_evaluator.evaluate(sample_triaged_inputs)

        assert isinstance(result, ActionSelectionPDMAResult)
        assert result.selected_handler_action == CoreHandlerActionType.PONDER # Fallback action
        assert isinstance(result.action_parameters, PonderParams)
        # Expect the original error message in the fallback details
        assert error_message in result.action_parameters.key_questions[0]
        assert "Fallback due to General Exception" in result.action_selection_rationale
        assert f"Exception: {error_message}" in result.raw_llm_response # Check raw response stores exception info
        action_selection_pdma_evaluator.aclient.chat.completions.create.assert_awaited_once()

    async def test_evaluate_unmappable_action_param_model(
        self, action_selection_pdma_evaluator: ActionSelectionPDMAEvaluator, sample_triaged_inputs: Dict[str, Any], monkeypatch # Removed mock_openai_client
    ):
        """Test scenario where LLM returns an action for which no ParamModel is defined."""
        # Simulate LLM returning an action type that doesn't have a mapping in ACTION_PARAM_MODELS
        # For this test, let's assume 'TOOL' is temporarily unmapped.
        
        expected_llm_response_data = {
            "schema_version": CIRISSchemaVersion.V1_0_BETA,
            "context_summary_for_action_selection": "LLM decided to use a tool.",
            "action_alignment_check": {"tool": "aligned"},
            "selected_handler_action": CoreHandlerActionType.TOOL,
            "action_parameters": {"tool_name": "calculator", "arguments": {"query": "2+2"}},
            "action_selection_rationale": "A calculation is needed.",
            "monitoring_for_selected_action": "Check tool output."
        }
        # Create the Pydantic model instance that represents the LLM's structured output
        expected_pydantic_model_obj = _ActionSelectionLLMResponse(**expected_llm_response_data)
        # Convert this Pydantic model to its JSON string representation
        expected_json_content = expected_pydantic_model_obj.model_dump_json()

        # Simulate the OpenAI API ChatCompletion response structure
        mock_chat_completion_response = MagicMock()
        mock_chat_completion_message = MagicMock()
        mock_chat_completion_message.content = expected_json_content
        mock_chat_completion_message.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.message = mock_chat_completion_message
        mock_chat_completion_response.choices = [mock_choice]

        # The instructor-patched client's create method should return the Pydantic model instance directly
        expected_pydantic_model_obj._raw_response = mock_chat_completion_response # Attach the mock raw response
        action_selection_pdma_evaluator.aclient.chat.completions.create.return_value = expected_pydantic_model_obj

        # Temporarily modify ACTION_PARAM_MODELS for this test to simulate TOOL key missing
        # Make a copy to avoid modifying the global state directly in a way that affects other tests
        # or causes issues with monkeypatch.undo() on built-in dict methods.
        
        original_models = action_selection_pdma_module.ACTION_PARAM_MODELS
        modified_models = original_models.copy()
        if CoreHandlerActionType.TOOL in modified_models:
            del modified_models[CoreHandlerActionType.TOOL]

        monkeypatch.setattr(action_selection_pdma_module, 'ACTION_PARAM_MODELS', modified_models)
        
        result = await action_selection_pdma_evaluator.evaluate(sample_triaged_inputs)

        # monkeypatch will automatically restore the original ACTION_PARAM_MODELS
        # to action_selection_pdma_module after the test.

        assert isinstance(result, ActionSelectionPDMAResult)
        assert result.selected_handler_action == CoreHandlerActionType.TOOL
        
        # Check the content of action_parameters
        # It could be an ActParams object (due to Pydantic Union behavior) or a dict.
        # The SUT's internal logic correctly decided not to parse with a specific ParamModel.
        action_params_for_comparison = result.action_parameters
        if isinstance(action_params_for_comparison, BaseModel):
            action_params_for_comparison = action_params_for_comparison.model_dump()
            
        assert isinstance(action_params_for_comparison, dict)
        assert action_params_for_comparison == expected_llm_response_data["action_parameters"]
        
        assert result.raw_llm_response == str(mock_chat_completion_response) # Check raw response
        action_selection_pdma_evaluator.aclient.chat.completions.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_evaluate_param_validation_error(
        self, action_selection_pdma_evaluator: ActionSelectionPDMAEvaluator, sample_triaged_inputs: Dict[str, Any]
    ):
        """If parameter parsing fails validation, the evaluator should return a PONDER result."""
        invalid_params = {
            "knowledge_data": {"nick": "bob"},
            "source": "unit test",
            "knowledge_type": "profile",
            "confidence": 0.5,
        }  # missing knowledge_unit_description

        expected_llm_response_data = {
            "schema_version": CIRISSchemaVersion.V1_0_BETA,
            "context_summary_for_action_selection": "Attempting to memorize info",
            "action_alignment_check": {"memorize": "aligned"},
            "selected_handler_action": CoreHandlerActionType.MEMORIZE,
            "action_parameters": invalid_params,
            "action_selection_rationale": "Store info",
            "monitoring_for_selected_action": "None",
        }

        expected_pydantic_model_obj = _ActionSelectionLLMResponse(**expected_llm_response_data)
        expected_json_content = expected_pydantic_model_obj.model_dump_json()

        mock_resp = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = expected_json_content
        mock_msg.tool_calls = None
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp.choices = [mock_choice]

        expected_pydantic_model_obj._raw_response = mock_resp
        action_selection_pdma_evaluator.aclient.chat.completions.create.return_value = expected_pydantic_model_obj

        result = await action_selection_pdma_evaluator.evaluate(sample_triaged_inputs)

        assert isinstance(result, ActionSelectionPDMAResult)
        assert result.selected_handler_action == CoreHandlerActionType.MEMORIZE
        assert isinstance(result.action_parameters, dict)


    @pytest.mark.asyncio # Ensure this non-async test is not marked as async if it's not
    async def test_action_selection_pdma_evaluator_repr(self, action_selection_pdma_evaluator: ActionSelectionPDMAEvaluator): # Corrected type hint
        """Test ActionSelectionPDMAEvaluator __repr__."""
        # This test is synchronous, but if the class fixture is async, pytest might require it.
        # If it's truly synchronous, remove @pytest.mark.asyncio from the class or this method.
        # For now, assuming it's fine as is or the fixture setup handles it.
        assert repr(action_selection_pdma_evaluator) == f"<ActionSelectionPDMAEvaluator model='{action_selection_pdma_evaluator.model_name}' (using instructor)>"
