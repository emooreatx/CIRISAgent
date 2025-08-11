"""Tests for Action Selection PDMA."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ciris_engine.logic.dma.action_selection_pdma import ActionSelectionPDMAEvaluator
from ciris_engine.schemas.dma.faculty import ConscienceFailureContext, EnhancedDMAInputs
from ciris_engine.schemas.dma.prompts import PromptCollection
from ciris_engine.schemas.dma.results import ActionSelectionResult
from ciris_engine.schemas.runtime.enums import HandlerActionType
from ciris_engine.schemas.runtime.models import Thought


class TestActionSelectionPDMAEvaluator:
    """Test suite for ActionSelectionPDMAEvaluator."""

    @pytest.fixture
    def mock_service_registry(self):
        """Create a mock service registry."""
        registry = Mock()
        registry.get_llm_service = Mock(return_value=AsyncMock())
        registry.get_memory_service = Mock(return_value=AsyncMock())
        return registry

    @pytest.fixture
    def mock_thought(self):
        """Create a mock thought."""
        thought = Mock(spec=Thought)
        thought.thought_id = "test-thought-123"
        thought.raw_content = "Test thought content"
        thought.state = "PENDING"
        thought.source = "TEST"
        return thought

    @pytest.fixture
    def mock_input_data(self, mock_thought):
        """Create mock enhanced DMA inputs."""
        inputs = Mock(spec=EnhancedDMAInputs)
        inputs.original_thought = mock_thought
        inputs.ethical_evaluation = {"action": "SPEAK", "reasoning": "Test reasoning"}
        inputs.csdma_evaluation = {"common_sense": True}
        inputs.dsdma_evaluation = {"domain_specific": True}
        inputs.combined_analysis = "Combined analysis"
        inputs.faculty_evaluations = {}
        return inputs

    @pytest.fixture
    def evaluator(self, mock_service_registry):
        """Create an ActionSelectionPDMAEvaluator instance."""
        with patch("ciris_engine.logic.dma.action_selection_pdma.ActionSelectionContextBuilder"):
            evaluator = ActionSelectionPDMAEvaluator(service_registry=mock_service_registry, model_name="test-model")
            evaluator.sink = AsyncMock()
            return evaluator

    @pytest.mark.asyncio
    async def test_evaluate_basic(self, evaluator, mock_input_data):
        """Test basic evaluation flow."""
        # Mock the LLM response
        evaluator.sink.dispatch.return_value = {
            "action": "SPEAK",
            "action_params": {"content": "Hello"},
            "explanation": "Responding to user",
        }

        result = await evaluator.evaluate(mock_input_data)

        assert isinstance(result, ActionSelectionResult)
        assert result.action == HandlerActionType.SPEAK
        assert result.action_params["content"] == "Hello"
        assert result.explanation == "Responding to user"

    @pytest.mark.asyncio
    async def test_evaluate_with_faculty(self, mock_service_registry, mock_input_data):
        """Test evaluation with faculty integration."""
        mock_faculty = Mock()
        mock_faculty.evaluate = AsyncMock(return_value={"insight": "test"})

        faculties = {"test_faculty": mock_faculty}

        with patch("ciris_engine.logic.dma.action_selection_pdma.ActionSelectionContextBuilder"):
            evaluator = ActionSelectionPDMAEvaluator(service_registry=mock_service_registry, faculties=faculties)
            evaluator.sink = AsyncMock()
            evaluator.sink.dispatch.return_value = {
                "action": "PONDER",
                "action_params": {},
                "explanation": "Need more thought",
            }

        result = await evaluator.evaluate(mock_input_data)

        assert result.action == HandlerActionType.PONDER

    @pytest.mark.asyncio
    async def test_evaluate_special_case_wakeup(self, evaluator):
        """Test special case handling for wakeup task."""
        # Create a wakeup task
        thought = Mock(spec=Thought)
        thought.thought_id = "wakeup-123"
        thought.raw_content = "WAKEUP"
        thought.state = "PENDING"
        thought.source = "SYSTEM"

        inputs = Mock(spec=EnhancedDMAInputs)
        inputs.original_thought = thought
        inputs.ethical_evaluation = {}
        inputs.csdma_evaluation = {}
        inputs.dsdma_evaluation = {}
        inputs.combined_analysis = ""
        inputs.faculty_evaluations = {}

        # Mock special case handler
        with patch.object(evaluator, "_handle_special_cases") as mock_special:
            mock_special.return_value = ActionSelectionResult(
                action=HandlerActionType.TASK_COMPLETE, action_params={}, explanation="Wakeup complete"
            )

            result = await evaluator.evaluate(inputs)

            assert result.action == HandlerActionType.TASK_COMPLETE
            mock_special.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_with_conscience_failure(self, evaluator, mock_input_data):
        """Test recursive evaluation on conscience failure."""
        # Add conscience failure context
        mock_input_data.conscience_failure_context = Mock(spec=ConscienceFailureContext)
        mock_input_data.conscience_failure_context.failure_reason = "Ethical concern"
        mock_input_data.conscience_failure_context.suggestions = ["Consider alternatives"]

        evaluator.sink.dispatch.return_value = {
            "action": "DEFER",
            "action_params": {"reason": "Ethical concern"},
            "explanation": "Deferring due to conscience failure",
        }

        result = await evaluator.evaluate(mock_input_data, enable_recursive_evaluation=True)

        assert result.action == HandlerActionType.DEFER
        assert "Ethical concern" in result.action_params["reason"]

    @pytest.mark.asyncio
    async def test_evaluate_invalid_input(self, evaluator):
        """Test evaluation with invalid input."""
        with pytest.raises(ValueError, match="input_data is required"):
            await evaluator.evaluate(None)

    @pytest.mark.asyncio
    async def test_evaluate_with_prompt_overrides(self, mock_service_registry, mock_input_data):
        """Test evaluation with custom prompt overrides."""
        prompts = PromptCollection(system_prompt="Custom system prompt", user_prompt="Custom user prompt")

        with patch("ciris_engine.logic.dma.action_selection_pdma.ActionSelectionContextBuilder"):
            evaluator = ActionSelectionPDMAEvaluator(service_registry=mock_service_registry, prompt_overrides=prompts)
            evaluator.sink = AsyncMock()
            evaluator.sink.dispatch.return_value = {
                "action": "OBSERVE",
                "action_params": {"message": "Observing"},
                "explanation": "Passive observation",
            }

        result = await evaluator.evaluate(mock_input_data)

        assert result.action == HandlerActionType.OBSERVE

    @pytest.mark.asyncio
    async def test_evaluate_with_retry_on_failure(self, evaluator, mock_input_data):
        """Test retry logic on evaluation failure."""
        # First call fails, second succeeds
        evaluator.sink.dispatch.side_effect = [
            Exception("LLM error"),
            {"action": "MEMORIZE", "action_params": {"data": "test"}, "explanation": "Storing memory"},
        ]

        with patch.object(evaluator, "max_retries", 2):
            result = await evaluator.evaluate(mock_input_data)

            assert result.action == HandlerActionType.MEMORIZE
            assert evaluator.sink.dispatch.call_count == 2

    def test_initialization(self, mock_service_registry):
        """Test proper initialization of evaluator."""
        with patch("ciris_engine.logic.dma.action_selection_pdma.ActionSelectionContextBuilder") as mock_builder:
            evaluator = ActionSelectionPDMAEvaluator(
                service_registry=mock_service_registry, model_name="custom-model", max_retries=5
            )

            assert evaluator.model_name == "custom-model"
            assert evaluator.max_retries == 5
            mock_builder.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_all_action_types(self, evaluator, mock_input_data):
        """Test evaluation can return all action types."""
        action_types = [
            HandlerActionType.SPEAK,
            HandlerActionType.TOOL,
            HandlerActionType.OBSERVE,
            HandlerActionType.REJECT,
            HandlerActionType.PONDER,
            HandlerActionType.DEFER,
            HandlerActionType.MEMORIZE,
            HandlerActionType.RECALL,
            HandlerActionType.FORGET,
            HandlerActionType.TASK_COMPLETE,
        ]

        for action_type in action_types:
            evaluator.sink.dispatch.return_value = {
                "action": action_type.value,
                "action_params": {},
                "explanation": f"Testing {action_type.value}",
            }

            result = await evaluator.evaluate(mock_input_data)
            assert result.action == action_type
