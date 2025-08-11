"""Tests for Common Sense DMA."""

from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ciris_engine.logic.dma.csdma import CSDMAEvaluator
from ciris_engine.logic.processors.support.processing_queue import ProcessingQueueItem
from ciris_engine.schemas.dma.results import CSDMAResult


class TestCSDMAEvaluator:
    """Test suite for CSDMAEvaluator."""

    @pytest.fixture
    def mock_service_registry(self):
        """Create a mock service registry."""
        registry = Mock()
        llm_service = AsyncMock()
        registry.get_llm_service = Mock(return_value=llm_service)
        registry.get_memory_service = Mock(return_value=AsyncMock())
        return registry

    @pytest.fixture
    def mock_queue_item(self):
        """Create a mock processing queue item."""
        item = Mock(spec=ProcessingQueueItem)
        item.thought = Mock()
        item.thought.raw_content = "Test thought content"
        item.thought.thought_id = "test-thought-123"
        item.task = Mock()
        item.task.instruction = "Test instruction"
        item.task.task_id = "test-task-456"
        item.context = {"test": "context"}
        return item

    @pytest.fixture
    def evaluator(self, mock_service_registry):
        """Create a CSDMAEvaluator instance."""
        with patch("ciris_engine.logic.dma.csdma.get_prompt_loader") as mock_loader:
            mock_prompt_collection = Mock()
            mock_prompt_collection.get_prompt.return_value = "Mock prompt"
            mock_loader.return_value.load_prompt_template.return_value = mock_prompt_collection
            evaluator = CSDMAEvaluator(service_registry=mock_service_registry, model_name="test-model")
            evaluator.sink = AsyncMock()
            return evaluator

    @pytest.mark.asyncio
    async def test_evaluate_common_sense_pass(self, evaluator, mock_queue_item):
        """Test evaluation that passes common sense check."""
        evaluator.sink.dispatch.return_value = CSDMAResult(
            passes_common_sense=True,
            confidence=0.9,
            reasoning="This makes logical sense",
            identified_issues=[],
            suggestions=["Proceed with action"],
            environmental_impact_assessment="Low impact",
            cultural_sensitivity_check="No concerns",
        )

        result = await evaluator.evaluate(mock_queue_item)

        assert isinstance(result, CSDMAResult)
        assert result.passes_common_sense is True
        assert result.confidence == 0.9
        assert result.reasoning == "This makes logical sense"
        assert len(result.identified_issues) == 0

    @pytest.mark.asyncio
    async def test_evaluate_common_sense_fail(self, evaluator, mock_queue_item):
        """Test evaluation that fails common sense check."""
        evaluator.sink.dispatch.return_value = CSDMAResult(
            passes_common_sense=False,
            confidence=0.2,
            reasoning="This violates physical laws",
            identified_issues=["Impossible physics", "Resource constraints"],
            suggestions=["Reconsider approach", "Check assumptions"],
            environmental_impact_assessment="High impact",
            cultural_sensitivity_check="Potential issues",
        )

        result = await evaluator.evaluate(mock_queue_item)

        assert result.passes_common_sense is False
        assert result.confidence == 0.2
        assert len(result.identified_issues) == 2
        assert "Impossible physics" in result.identified_issues

    @pytest.mark.asyncio
    async def test_evaluate_with_environmental_kg(self, mock_service_registry, mock_queue_item):
        """Test evaluation with environmental knowledge graph."""
        environmental_kg = {"physics": "laws", "resources": "constraints"}

        with patch("ciris_engine.logic.dma.csdma.get_prompt_loader") as mock_loader:
            mock_prompt_collection = Mock()
            mock_prompt_collection.get_prompt.return_value = "Mock prompt"
            mock_loader.return_value.load_prompt_template.return_value = mock_prompt_collection
            evaluator = CSDMAEvaluator(service_registry=mock_service_registry, environmental_kg=environmental_kg)
            evaluator.sink = AsyncMock()
            evaluator.sink.dispatch.return_value = CSDMAResult(
                passes_common_sense=True, confidence=0.8, reasoning="Environmental context considered"
            )

        result = await evaluator.evaluate(mock_queue_item)
        assert result.passes_common_sense is True
        assert "Environmental context" in result.reasoning

    @pytest.mark.asyncio
    async def test_evaluate_with_task_specific_kg(self, mock_service_registry, mock_queue_item):
        """Test evaluation with task-specific knowledge graph."""
        task_kg = {"domain": "specific", "rules": "applied"}

        with patch("ciris_engine.logic.dma.csdma.get_prompt_loader") as mock_loader:
            mock_prompt_collection = Mock()
            mock_prompt_collection.get_prompt.return_value = "Mock prompt"
            mock_loader.return_value.load_prompt_template.return_value = mock_prompt_collection
            evaluator = CSDMAEvaluator(service_registry=mock_service_registry, task_specific_kg=task_kg)
            evaluator.sink = AsyncMock()
            evaluator.sink.dispatch.return_value = CSDMAResult(
                passes_common_sense=True, confidence=0.85, reasoning="Task-specific rules applied"
            )

        result = await evaluator.evaluate(mock_queue_item)
        assert "Task-specific" in result.reasoning

    @pytest.mark.asyncio
    async def test_evaluate_with_prompt_overrides(self, mock_service_registry, mock_queue_item):
        """Test evaluation with custom prompt overrides."""
        overrides = {"system": "Custom system prompt", "user": "Custom user prompt"}

        with patch("ciris_engine.logic.dma.csdma.get_prompt_loader") as mock_loader:
            mock_loader.return_value.load_prompt_template.return_value = {
                "system": "Default system",
                "user": "Default user",
            }
            evaluator = CSDMAEvaluator(service_registry=mock_service_registry, prompt_overrides=overrides)
            evaluator.sink = AsyncMock()
            evaluator.sink.dispatch.return_value = CSDMAResult(
                passes_common_sense=True, confidence=0.75, reasoning="Custom prompts used"
            )

        result = await evaluator.evaluate(mock_queue_item)
        assert result.confidence == 0.75

    @pytest.mark.asyncio
    async def test_evaluate_invalid_input(self, evaluator):
        """Test evaluation with invalid input."""
        with pytest.raises(AttributeError):
            await evaluator.evaluate(None)

    @pytest.mark.asyncio
    async def test_evaluate_with_retry(self, evaluator, mock_queue_item):
        """Test retry logic on evaluation failure."""
        # First call fails, second succeeds
        evaluator.sink.dispatch.side_effect = [
            Exception("LLM error"),
            CSDMAResult(passes_common_sense=True, confidence=0.7, reasoning="Retry successful"),
        ]

        with patch.object(evaluator, "max_retries", 2):
            result = await evaluator.evaluate(mock_queue_item)

            assert result.passes_common_sense is True
            assert evaluator.sink.dispatch.call_count == 2

    @pytest.mark.asyncio
    async def test_evaluate_confidence_levels(self, evaluator, mock_queue_item):
        """Test various confidence levels."""
        confidence_levels = [0.0, 0.25, 0.5, 0.75, 1.0]

        for confidence in confidence_levels:
            evaluator.sink.dispatch.return_value = CSDMAResult(
                passes_common_sense=(confidence > 0.5),
                confidence=confidence,
                reasoning=f"Confidence level {confidence}",
            )

            result = await evaluator.evaluate(mock_queue_item)
            assert result.confidence == confidence
            assert result.passes_common_sense == (confidence > 0.5)

    @pytest.mark.asyncio
    async def test_evaluate_with_cultural_sensitivity(self, evaluator, mock_queue_item):
        """Test cultural sensitivity check in evaluation."""
        evaluator.sink.dispatch.return_value = CSDMAResult(
            passes_common_sense=True,
            confidence=0.8,
            reasoning="Culturally appropriate",
            cultural_sensitivity_check="Verified against multiple cultural contexts",
        )

        result = await evaluator.evaluate(mock_queue_item)
        assert result.cultural_sensitivity_check == "Verified against multiple cultural contexts"

    @pytest.mark.asyncio
    async def test_evaluate_environmental_impact(self, evaluator, mock_queue_item):
        """Test environmental impact assessment."""
        evaluator.sink.dispatch.return_value = CSDMAResult(
            passes_common_sense=True,
            confidence=0.9,
            reasoning="Environmentally sound",
            environmental_impact_assessment="Minimal carbon footprint, sustainable approach",
        )

        result = await evaluator.evaluate(mock_queue_item)
        assert "Minimal carbon footprint" in result.environmental_impact_assessment

    def test_initialization(self, mock_service_registry):
        """Test proper initialization of evaluator."""
        with patch("ciris_engine.logic.dma.csdma.get_prompt_loader") as mock_loader:
            mock_prompt_collection = Mock()
            mock_prompt_collection.get_prompt.return_value = "Mock prompt"
            mock_loader.return_value.load_prompt_template.return_value = mock_prompt_collection

            evaluator = CSDMAEvaluator(service_registry=mock_service_registry, model_name="custom-model", max_retries=5)

            assert evaluator.model_name == "custom-model"
            assert evaluator.max_retries == 5
            mock_loader.assert_called_once()
