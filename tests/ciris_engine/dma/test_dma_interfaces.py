"""Tests for DMA interface protocols and compliance."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional

from ciris_engine.protocols.dma_interface import (
    BaseDMAInterface,
    EthicalDMAInterface,
    CSDMAInterface,
    DSDMAInterface,
    ActionSelectionDMAInterface,
)
from ciris_engine.protocols.faculties import EpistemicFaculty
from ciris_engine.registries.base import ServiceRegistry
from ciris_engine.processor.processing_queue import ProcessingQueueItem, ThoughtContent
from ciris_engine.schemas.context_schemas_v1 import ThoughtContext
from ciris_engine.schemas.dma_results_v1 import (
    EthicalDMAResult,
    CSDMAResult,
    DSDMAResult,
    ActionSelectionResult,
)
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtType
from ciris_engine.schemas.action_params_v1 import SpeakParams
from datetime import datetime
from pydantic import BaseModel


class MockFaculty:
    """Mock epistemic faculty for testing."""
    
    async def evaluate(self, content: str, context: Optional[Dict[str, Any]] = None) -> BaseModel:
        class MockResult(BaseModel):
            score: float = 0.8
            reasoning: str = "Mock faculty evaluation"
        
        return MockResult()


class TestBaseDMAInterface:
    """Test the base DMA interface functionality."""
    
    @pytest.fixture
    def mock_service_registry(self):
        registry = MagicMock(spec=ServiceRegistry)
        mock_service = AsyncMock()
        registry.get_service.return_value = mock_service
        return registry
    
    @pytest.fixture
    def mock_faculties(self):
        return {"mock_faculty": MockFaculty()}
    
    def test_base_dma_interface_initialization(self, mock_service_registry, mock_faculties):
        """Test BaseDMAInterface initialization."""
        
        class TestDMA(BaseDMAInterface):
            async def evaluate(self, input_data, **kwargs):
                return BaseModel()
        
        dma = TestDMA(
            service_registry=mock_service_registry,
            model_name="test-model",
            max_retries=3,
            prompt_overrides={"test": "value"},
            faculties=mock_faculties
        )
        
        assert dma.service_registry == mock_service_registry
        assert dma.model_name == "test-model"
        assert dma.max_retries == 3
        assert dma.faculties == mock_faculties
        assert dma.prompts == {"test": "value"}
    
    @pytest.mark.asyncio
    async def test_get_llm_service(self, mock_service_registry):
        """Test LLM service retrieval."""
        
        class TestDMA(BaseDMAInterface):
            async def evaluate(self, input_data, **kwargs):
                return BaseModel()
        
        dma = TestDMA(service_registry=mock_service_registry)
        
        service = await dma.get_llm_service()
        
        mock_service_registry.get_service.assert_called_once_with(
            handler="TestDMA",
            service_type="llm"
        )
    
    @pytest.mark.asyncio
    async def test_apply_faculties(self, mock_service_registry, mock_faculties):
        """Test applying epistemic faculties."""
        
        class TestDMA(BaseDMAInterface):
            async def evaluate(self, input_data, **kwargs):
                return BaseModel()
        
        dma = TestDMA(
            service_registry=mock_service_registry,
            faculties=mock_faculties
        )
        
        results = await dma.apply_faculties("test content", {"test": "context"})
        
        assert "mock_faculty" in results
        assert results["mock_faculty"].score == 0.8
        assert results["mock_faculty"].reasoning == "Mock faculty evaluation"
    
    @pytest.mark.asyncio
    async def test_apply_faculties_handles_errors(self, mock_service_registry):
        """Test that faculty errors don't crash the evaluation."""
        
        class FailingFaculty:
            async def evaluate(self, content, context=None):
                raise Exception("Faculty failed")
        
        class TestDMA(BaseDMAInterface):
            async def evaluate(self, input_data, **kwargs):
                return BaseModel()
        
        dma = TestDMA(
            service_registry=mock_service_registry,
            faculties={"failing": FailingFaculty()}
        )
        
        # Should not raise exception
        results = await dma.apply_faculties("test content")
        
        # Should return empty results for failed faculty
        assert results == {}


class TestEthicalDMAInterface:
    """Test the ethical DMA interface."""
    
    @pytest.fixture
    def mock_service_registry(self):
        registry = MagicMock(spec=ServiceRegistry)
        return registry
    
    @pytest.fixture
    def mock_thought_item(self):
        return ProcessingQueueItem(
            thought_id="test-123",
            content=ThoughtContent(text="Test thought content"),
            source_task_id="test-task-123",
            thought_type=ThoughtType.STANDARD
        )
    
    @pytest.fixture
    def mock_context(self):
        from ciris_engine.schemas.context_schemas_v1 import SystemSnapshot
        return ThoughtContext(
            identity_context="test context",
            system_snapshot=SystemSnapshot(),
            user_profiles={}
        )
    
    def test_ethical_dma_interface_signature(self, mock_service_registry):
        """Test that EthicalDMAInterface has correct method signature."""
        
        class TestEthicalDMA(EthicalDMAInterface):
            async def evaluate(self, thought_item, context=None, **kwargs):
                return EthicalDMAResult(
                    alignment_check={"test": "pass"},
                    decision="approved",
                    rationale="Test rationale"
                )
        
        dma = TestEthicalDMA(service_registry=mock_service_registry)
        assert callable(dma.evaluate)
    
    @pytest.mark.asyncio
    async def test_ethical_dma_evaluate(self, mock_service_registry, mock_thought_item, mock_context):
        """Test ethical DMA evaluation."""
        
        class TestEthicalDMA(EthicalDMAInterface):
            async def evaluate(self, thought_item, context=None, **kwargs):
                return EthicalDMAResult(
                    alignment_check={"do_good": "aligned", "avoid_harm": "aligned"},
                    decision="approved",
                    rationale="Content aligns with ethical principles"
                )
        
        dma = TestEthicalDMA(service_registry=mock_service_registry)
        result = await dma.evaluate(mock_thought_item, mock_context)
        
        assert isinstance(result, EthicalDMAResult)
        assert result.decision == "approved"
        assert "do_good" in result.alignment_check
        assert result.rationale == "Content aligns with ethical principles"


class TestCSDMAInterface:
    """Test the common sense DMA interface."""
    
    @pytest.fixture
    def mock_service_registry(self):
        return MagicMock(spec=ServiceRegistry)
    
    @pytest.fixture
    def mock_thought_item(self):
        return ProcessingQueueItem(
            thought_id="test-456",
            content=ThoughtContent(text="Test common sense content"),
            source_task_id="test-task-456",
            thought_type=ThoughtType.STANDARD
        )
    
    @pytest.mark.asyncio
    async def test_csdma_evaluate(self, mock_service_registry, mock_thought_item):
        """Test CSDMA evaluation."""
        
        class TestCSDMA(CSDMAInterface):
            async def evaluate(self, thought_item, **kwargs):
                return CSDMAResult(
                    plausibility_score=0.85,
                    flags=["minor_ambiguity"],
                    reasoning="Content is generally plausible with minor ambiguity"
                )
        
        dma = TestCSDMA(service_registry=mock_service_registry)
        result = await dma.evaluate(mock_thought_item)
        
        assert isinstance(result, CSDMAResult)
        assert result.plausibility_score == 0.85
        assert "minor_ambiguity" in result.flags
        assert "plausible" in result.reasoning


class TestDSDMAInterface:
    """Test the domain-specific DMA interface."""
    
    @pytest.fixture
    def mock_service_registry(self):
        return MagicMock(spec=ServiceRegistry)
    
    @pytest.fixture
    def mock_thought_item(self):
        return ProcessingQueueItem(
            thought_id="test-789",
            content=ThoughtContent(text="Domain-specific content"),
            source_task_id="test-task-789",
            thought_type=ThoughtType.STANDARD
        )
    
    @pytest.mark.asyncio
    async def test_dsdma_evaluate(self, mock_service_registry, mock_thought_item):
        """Test DSDMA evaluation."""
        
        class TestDSDMA(DSDMAInterface):
            async def evaluate(self, thought_item, current_context=None, **kwargs):
                return DSDMAResult(
                    domain="test_domain",
                    score=0.9,
                    flags=["domain_specific_flag"],
                    reasoning="Content aligns well with domain expertise",
                    recommended_action="proceed"
                )
        
        dma = TestDSDMA(service_registry=mock_service_registry)
        result = await dma.evaluate(
            mock_thought_item, 
            current_context={"domain": "test"}
        )
        
        assert isinstance(result, DSDMAResult)
        assert result.domain == "test_domain"
        assert result.score == 0.9
        assert result.recommended_action == "proceed"


class TestActionSelectionDMAInterface:
    """Test the action selection DMA interface."""
    
    @pytest.fixture
    def mock_service_registry(self):
        return MagicMock(spec=ServiceRegistry)
    
    @pytest.fixture
    def mock_faculties(self):
        return {"entropy": MockFaculty(), "coherence": MockFaculty()}
    
    @pytest.fixture
    def mock_triaged_inputs(self):
        from ciris_engine.schemas.agent_core_schemas_v1 import Thought
        
        return {
            "original_thought": Thought(
                thought_id="test-action",
                content="Test action selection",
                thought_type=ThoughtType.STANDARD,
                source_task_id="test-task",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            ),
            "ethical_pdma_result": EthicalDMAResult(
                alignment_check={"test": "pass"},
                decision="approved"
            ),
            "csdma_result": CSDMAResult(
                plausibility_score=0.8,
                reasoning="Plausible"
            ),
            "dsdma_result": DSDMAResult(
                domain="test",
                score=0.7,
                reasoning="Domain appropriate"
            ),
            "current_ponder_count": 0,
            "max_rounds": 3
        }
    
    @pytest.mark.asyncio
    async def test_action_selection_evaluate(self, mock_service_registry, mock_triaged_inputs):
        """Test action selection evaluation."""
        
        class TestActionSelectionDMA(ActionSelectionDMAInterface):
            async def evaluate(self, triaged_inputs, enable_recursive_evaluation=False, **kwargs):
                return ActionSelectionResult(
                    selected_action=HandlerActionType.SPEAK,
                    action_parameters=SpeakParams(content="Test response"),
                    rationale="Selected SPEAK based on evaluation"
                )
            
            async def recursive_evaluate_with_faculties(self, triaged_inputs, guardrail_failure_context):
                # Enhanced evaluation with faculties
                return ActionSelectionResult(
                    selected_action=HandlerActionType.PONDER,
                    action_parameters={"questions": ["Enhanced question"]},
                    rationale="Recursive evaluation with faculty insights"
                )
        
        dma = TestActionSelectionDMA(service_registry=mock_service_registry)
        
        # Test normal evaluation
        result = await dma.evaluate(mock_triaged_inputs)
        assert isinstance(result, ActionSelectionResult)
        assert result.selected_action == HandlerActionType.SPEAK
        
        # Test recursive evaluation
        recursive_result = await dma.recursive_evaluate_with_faculties(
            mock_triaged_inputs,
            {"failure_reason": "test"}
        )
        assert recursive_result.selected_action == HandlerActionType.PONDER
        assert "faculty insights" in recursive_result.rationale
    
    @pytest.mark.asyncio
    async def test_action_selection_with_faculties(self, mock_service_registry, mock_faculties, mock_triaged_inputs):
        """Test action selection with faculty integration."""
        
        class TestActionSelectionDMA(ActionSelectionDMAInterface):
            async def evaluate(self, triaged_inputs, enable_recursive_evaluation=False, **kwargs):
                # Simulate using faculties
                if self.faculties and triaged_inputs.get("faculty_evaluations"):
                    return ActionSelectionResult(
                        selected_action=HandlerActionType.DEFER,
                        action_parameters={"reason": "Faculty evaluation suggested deferral"},
                        rationale="Based on faculty insights, deferring to wise authority"
                    )
                else:
                    return ActionSelectionResult(
                        selected_action=HandlerActionType.SPEAK,
                        action_parameters=SpeakParams(content="Normal response"),
                        rationale="Standard evaluation"
                    )
            
            async def recursive_evaluate_with_faculties(self, triaged_inputs, guardrail_failure_context):
                # Apply faculties first
                enhanced_inputs = await self._enhance_with_faculties(triaged_inputs)
                return await self.evaluate(enhanced_inputs)
            
            async def _enhance_with_faculties(self, triaged_inputs):
                faculty_results = await self.apply_faculties("test content")
                return {
                    **triaged_inputs,
                    "faculty_evaluations": faculty_results
                }
        
        dma = TestActionSelectionDMA(
            service_registry=mock_service_registry,
            faculties=mock_faculties
        )
        
        # Test with faculty enhancement
        result = await dma.recursive_evaluate_with_faculties(
            mock_triaged_inputs,
            {"test": "context"}
        )
        
        assert result.selected_action == HandlerActionType.DEFER
        assert "faculty insights" in result.rationale


class TestDMAProtocolCompliance:
    """Test that all DMA interfaces are properly defined."""
    
    def test_all_interfaces_exist(self):
        """Test that all expected DMA interfaces are defined."""
        interfaces = [
            BaseDMAInterface,
            EthicalDMAInterface,
            CSDMAInterface,
            DSDMAInterface,
            ActionSelectionDMAInterface,
        ]
        
        for interface in interfaces:
            assert interface is not None
            assert hasattr(interface, 'evaluate')
    
    def test_interface_inheritance(self):
        """Test that specific interfaces inherit from BaseDMAInterface."""
        specific_interfaces = [
            EthicalDMAInterface,
            CSDMAInterface,
            DSDMAInterface,
            ActionSelectionDMAInterface,
        ]
        
        for interface in specific_interfaces:
            # Check if it has the base interface in its MRO or similar
            assert hasattr(interface, 'apply_faculties')
            assert hasattr(interface, 'get_llm_service')
    
    def test_evaluate_method_signatures(self):
        """Test that evaluate methods have proper signatures."""
        import inspect
        
        # Check EthicalDMAInterface
        sig = inspect.signature(EthicalDMAInterface.evaluate)
        params = list(sig.parameters.keys())
        assert 'self' in params
        assert 'thought_item' in params
        assert 'context' in params
        assert 'kwargs' in params
        
        # Check ActionSelectionDMAInterface
        sig = inspect.signature(ActionSelectionDMAInterface.evaluate)
        params = list(sig.parameters.keys())
        assert 'triaged_inputs' in params
        assert 'enable_recursive_evaluation' in params