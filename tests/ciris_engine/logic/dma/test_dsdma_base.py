"""Tests for Domain-Specific DMA Base."""

from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ciris_engine.logic.dma.dsdma_base import BaseDSDMA
from ciris_engine.logic.processors.support.processing_queue import ProcessingQueueItem
from ciris_engine.schemas.dma.results import DSDMAResult


class ConcreteDSDMA(BaseDSDMA):
    """Concrete implementation for testing."""

    pass


class TestBaseDSDMA:
    """Test suite for BaseDSDMA."""

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
        item.thought.raw_content = "Test domain-specific thought"
        item.thought.thought_id = "domain-thought-123"
        item.task = Mock()
        item.task.instruction = "Domain task"
        item.task.task_id = "domain-task-456"
        item.context = {"domain": "test"}
        return item

    @pytest.fixture
    def evaluator(self, mock_service_registry):
        """Create a BaseDSDMA instance."""
        with patch("ciris_engine.logic.dma.dsdma_base.get_prompt_loader") as mock_loader:
            mock_prompt_collection = Mock()
            mock_prompt_collection.get_prompt.return_value = "Mock prompt"
            mock_loader.return_value.load_prompt_template.return_value = mock_prompt_collection
            evaluator = ConcreteDSDMA(
                domain_name="test_domain", service_registry=mock_service_registry, model_name="test-model"
            )
            evaluator.sink = AsyncMock()
            return evaluator

    @pytest.mark.asyncio
    async def test_evaluate_domain_aligned(self, evaluator, mock_queue_item):
        """Test evaluation that is aligned with domain."""
        evaluator.sink.dispatch.return_value = DSDMAResult(
            is_domain_aligned=True,
            confidence=0.95,
            reasoning="Perfectly aligned with domain rules",
            domain_specific_insights=["Follows best practices", "Uses appropriate tools"],
            recommended_adjustments=[],
            domain_constraints_violated=[],
            domain_opportunities_identified=["Optimization possible"],
        )

        result = await evaluator.evaluate(mock_queue_item)

        assert isinstance(result, DSDMAResult)
        assert result.is_domain_aligned is True
        assert result.confidence == 0.95
        assert len(result.domain_specific_insights) == 2
        assert len(result.domain_constraints_violated) == 0

    @pytest.mark.asyncio
    async def test_evaluate_domain_misaligned(self, evaluator, mock_queue_item):
        """Test evaluation that violates domain constraints."""
        evaluator.sink.dispatch.return_value = DSDMAResult(
            is_domain_aligned=False,
            confidence=0.3,
            reasoning="Violates multiple domain constraints",
            domain_specific_insights=["Poor tool choice"],
            recommended_adjustments=["Use domain-specific tool", "Follow protocol"],
            domain_constraints_violated=["Constraint A", "Constraint B"],
            domain_opportunities_identified=[],
        )

        result = await evaluator.evaluate(mock_queue_item)

        assert result.is_domain_aligned is False
        assert result.confidence == 0.3
        assert len(result.domain_constraints_violated) == 2
        assert "Constraint A" in result.domain_constraints_violated
        assert len(result.recommended_adjustments) == 2

    @pytest.mark.asyncio
    async def test_evaluate_with_domain_specific_knowledge(self, mock_service_registry, mock_queue_item):
        """Test evaluation with domain-specific knowledge."""
        domain_knowledge = {
            "rules": ["Rule 1", "Rule 2"],
            "best_practices": ["Practice A", "Practice B"],
            "constraints": {"max_size": 100},
        }

        with patch("ciris_engine.logic.dma.dsdma_base.get_prompt_loader") as mock_loader:
            mock_prompt_collection = Mock()
            mock_prompt_collection.get_prompt.return_value = "Mock prompt"
            mock_loader.return_value.load_prompt_template.return_value = mock_prompt_collection
            evaluator = ConcreteDSDMA(
                domain_name="specialized_domain",
                service_registry=mock_service_registry,
                domain_specific_knowledge=domain_knowledge,
            )
            evaluator.sink = AsyncMock()
            evaluator.sink.dispatch.return_value = DSDMAResult(
                is_domain_aligned=True,
                confidence=0.9,
                reasoning="Knowledge applied successfully",
                domain_specific_insights=["Rule 1 followed", "Practice A applied"],
            )

        result = await evaluator.evaluate(mock_queue_item)
        assert result.is_domain_aligned is True
        assert "Rule 1 followed" in result.domain_specific_insights

    @pytest.mark.asyncio
    async def test_evaluate_with_custom_prompt_template(self, mock_service_registry, mock_queue_item):
        """Test evaluation with custom prompt template."""
        custom_template = "Custom domain evaluation for {domain_name}"

        with patch("ciris_engine.logic.dma.dsdma_base.get_prompt_loader") as mock_loader:
            mock_prompt_collection = Mock()
            mock_prompt_collection.get_prompt.return_value = "Mock prompt"
            mock_loader.return_value.load_prompt_template.return_value = mock_prompt_collection
            evaluator = ConcreteDSDMA(
                domain_name="custom_domain", service_registry=mock_service_registry, prompt_template=custom_template
            )
            evaluator.sink = AsyncMock()
            evaluator.sink.dispatch.return_value = DSDMAResult(
                is_domain_aligned=True, confidence=0.85, reasoning="Custom template used"
            )

        result = await evaluator.evaluate(mock_queue_item)
        assert result.confidence == 0.85

    @pytest.mark.asyncio
    async def test_evaluate_opportunities_identified(self, evaluator, mock_queue_item):
        """Test identification of domain opportunities."""
        evaluator.sink.dispatch.return_value = DSDMAResult(
            is_domain_aligned=True,
            confidence=0.8,
            reasoning="Good alignment with opportunities",
            domain_opportunities_identified=[
                "Can leverage domain-specific API",
                "Opportunity for caching",
                "Parallel processing possible",
            ],
        )

        result = await evaluator.evaluate(mock_queue_item)
        assert len(result.domain_opportunities_identified) == 3
        assert "caching" in result.domain_opportunities_identified[1]

    @pytest.mark.asyncio
    async def test_evaluate_multiple_domains(self, mock_service_registry, mock_queue_item):
        """Test multiple domain evaluators."""
        domains = ["healthcare", "finance", "education"]

        for domain in domains:
            with patch("ciris_engine.logic.dma.dsdma_base.get_prompt_loader") as mock_loader:
                mock_loader.return_value.load_prompt_template.return_value = {
                    "system": f"{domain} system",
                    "user": f"{domain} user",
                }
                evaluator = ConcreteDSDMA(domain_name=domain, service_registry=mock_service_registry)
                evaluator.sink = AsyncMock()
                evaluator.sink.dispatch.return_value = DSDMAResult(
                    is_domain_aligned=True,
                    confidence=0.7 + (0.1 * domains.index(domain)),
                    reasoning=f"Aligned with {domain}",
                )

                result = await evaluator.evaluate(mock_queue_item)
                assert domain in result.reasoning

    @pytest.mark.asyncio
    async def test_evaluate_with_retry(self, evaluator, mock_queue_item):
        """Test retry logic on evaluation failure."""
        # First call fails, second succeeds
        evaluator.sink.dispatch.side_effect = [
            Exception("LLM error"),
            DSDMAResult(is_domain_aligned=True, confidence=0.75, reasoning="Retry successful"),
        ]

        result = await evaluator.evaluate(mock_queue_item)

        assert result.is_domain_aligned is True
        assert evaluator.sink.dispatch.call_count == 2

    @pytest.mark.asyncio
    async def test_evaluate_tool_specific_domain(self, evaluator, mock_queue_item):
        """Test domain evaluation for tool-specific actions."""
        evaluator.sink.dispatch.return_value = DSDMAResult(
            is_domain_aligned=True,
            confidence=0.9,
            reasoning="Tool usage aligns with domain",
            domain_specific_insights=["Appropriate tool selected", "Tool parameters match domain requirements"],
            recommended_adjustments=["Consider tool rate limits"],
        )

        result = await evaluator.evaluate(mock_queue_item)
        assert "Appropriate tool selected" in result.domain_specific_insights
        assert "rate limits" in result.recommended_adjustments[0]

    def test_initialization_with_defaults(self, mock_service_registry):
        """Test initialization with default values."""
        with patch("ciris_engine.logic.dma.dsdma_base.get_prompt_loader") as mock_loader:
            mock_prompt_collection = Mock()
            mock_prompt_collection.get_prompt.return_value = "Mock prompt"
            mock_loader.return_value.load_prompt_template.return_value = mock_prompt_collection

            evaluator = ConcreteDSDMA(domain_name="default_domain", service_registry=mock_service_registry)

            assert evaluator.domain_name == "default_domain"
            assert evaluator.domain_specific_knowledge == {}
            assert evaluator.model_name == "gpt-4"  # Default model

    def test_initialization_with_all_params(self, mock_service_registry):
        """Test initialization with all parameters."""
        domain_knowledge = {"key": "value"}

        with patch("ciris_engine.logic.dma.dsdma_base.get_prompt_loader") as mock_loader:
            mock_prompt_collection = Mock()
            mock_prompt_collection.get_prompt.return_value = "Mock prompt"
            mock_loader.return_value.load_prompt_template.return_value = mock_prompt_collection

            evaluator = ConcreteDSDMA(
                domain_name="full_domain",
                service_registry=mock_service_registry,
                model_name="custom-model",
                domain_specific_knowledge=domain_knowledge,
                prompt_template="Custom template",
            )

            assert evaluator.domain_name == "full_domain"
            assert evaluator.model_name == "custom-model"
            assert evaluator.domain_specific_knowledge == domain_knowledge
