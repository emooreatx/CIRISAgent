"""
Tests for ModerationDSDMA integration
"""
import pytest
from unittest.mock import Mock, AsyncMock
from ciris_engine.dma.moderation_dsdma import ModerationDSDMA
from ciris_engine.dma.factory import create_dsdma_from_profile, DSDMA_CLASS_REGISTRY
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, ThoughtType
from ciris_engine.schemas.config_schemas_v1 import AgentProfile
from ciris_engine.registries.base import ServiceRegistry


class TestModerationDSDMA:
    """Test ModerationDSDMA functionality"""
    
    def test_registry_includes_moderation_dsdma(self):
        """Test that ModerationDSDMA is registered in the factory"""
        assert "ModerationDSDMA" in DSDMA_CLASS_REGISTRY
        assert DSDMA_CLASS_REGISTRY["ModerationDSDMA"] == ModerationDSDMA
    
    def test_moderation_dsdma_initialization(self):
        """Test ModerationDSDMA can be initialized with defaults"""
        mock_registry = Mock(spec=ServiceRegistry)
        
        dsdma = ModerationDSDMA(
            domain_name="test_moderation",
            service_registry=mock_registry,
            model_name="gpt-4o-mini"
        )
        
        assert dsdma.domain_name == "test_moderation"
        assert dsdma.model_name == "gpt-4o-mini"
        assert dsdma.service_registry == mock_registry
        
        # Check default knowledge was set
        assert "rules_summary" in dsdma.domain_specific_knowledge
        assert "moderation_tools" in dsdma.domain_specific_knowledge
        assert "escalation_triggers" in dsdma.domain_specific_knowledge
        assert "response_ladder" in dsdma.domain_specific_knowledge
    
    def test_moderation_dsdma_custom_knowledge(self):
        """Test ModerationDSDMA accepts custom domain knowledge"""
        mock_registry = Mock(spec=ServiceRegistry)
        custom_knowledge = {
            "rules_summary": "Custom rules",
            "custom_field": "custom_value"
        }
        
        dsdma = ModerationDSDMA(
            domain_name="custom_moderation",
            service_registry=mock_registry,
            domain_specific_knowledge=custom_knowledge
        )
        
        assert dsdma.domain_specific_knowledge == custom_knowledge
        assert dsdma.domain_specific_knowledge["rules_summary"] == "Custom rules"
        assert dsdma.domain_specific_knowledge["custom_field"] == "custom_value"
    
    @pytest.mark.asyncio
    async def test_create_dsdma_from_echo_profile(self):
        """Test that echo profile can create ModerationDSDMA"""
        from ciris_engine.schemas.config_schemas_v1 import ensure_models_rebuilt
        ensure_models_rebuilt()
        
        mock_registry = Mock(spec=ServiceRegistry)
        
        # Create a mock echo profile
        echo_profile = AgentProfile(
            name="echo",
            dsdma_identifier="ModerationDSDMA",
            dsdma_kwargs={
                "domain_specific_knowledge": {
                    "rules_summary": "Echo moderation rules"
                }
            }
        )
        
        dsdma = await create_dsdma_from_profile(
            echo_profile,
            mock_registry,
            model_name="gpt-4o-mini"
        )
        
        assert dsdma is not None
        assert isinstance(dsdma, ModerationDSDMA)
        assert dsdma.domain_name == "echo"
        assert dsdma.model_name == "gpt-4o-mini"
        assert dsdma.domain_specific_knowledge["rules_summary"] == "Echo moderation rules"
    
    def test_should_send_deferral_escalation_triggers(self):
        """Test escalation trigger detection"""
        mock_registry = Mock(spec=ServiceRegistry)
        dsdma = ModerationDSDMA(service_registry=mock_registry)
        
        # Test escalation triggers
        assert dsdma._should_send_deferral("I want to hurt myself", [])
        assert dsdma._should_send_deferral("This is a complex interpersonal conflict", [])
        assert dsdma._should_send_deferral("potential legal issues here", [])
        
        # Test normal content
        assert not dsdma._should_send_deferral("Hello everyone!", [])
        assert not dsdma._should_send_deferral("Can someone help me?", [])
    
    def test_should_send_deferral_complexity_flags(self):
        """Test deferral based on complexity flags"""
        mock_registry = Mock(spec=ServiceRegistry)
        dsdma = ModerationDSDMA(service_registry=mock_registry)
        
        # Test complexity flags
        assert dsdma._should_send_deferral("Normal message", ["complex_conflict"])
        assert dsdma._should_send_deferral("Normal message", ["legal_concern"])
        assert dsdma._should_send_deferral("Normal message", ["welfare_risk"])
        
        # Test normal flags
        assert not dsdma._should_send_deferral("Normal message", ["spam"])
        assert not dsdma._should_send_deferral("Normal message", ["new_user"])
    
    @pytest.mark.asyncio
    async def test_evaluate_thought_context_enrichment(self):
        """Test that evaluate_thought enriches context with moderation data"""
        from ciris_engine.schemas.dma_results_v1 import DSDMAResult
        mock_registry = Mock(spec=ServiceRegistry)
        
        # Create DSDMA instance
        dsdma = ModerationDSDMA(service_registry=mock_registry)
        
        # Mock the parent evaluate_thought method to return expected result
        async def mock_parent_evaluate_thought(self, thought_item, context):
            return DSDMAResult(
                domain="discord_moderation",
                score=0.8,
                recommended_action="none",
                flags=[],
                reasoning="Test reasoning"
            )
        
        # Patch the super().evaluate_thought call
        import ciris_engine.dma.dsdma_base
        original_evaluate = ciris_engine.dma.dsdma_base.BaseDSDMA.evaluate_thought
        ciris_engine.dma.dsdma_base.BaseDSDMA.evaluate_thought = mock_parent_evaluate_thought
        
        try:
            # Create test thought
            thought = Thought(
                thought_id="test_thought",
                source_task_id="test_task",
                thought_type=ThoughtType.OBSERVATION,
                content="Hello @everyone! THIS IS URGENT!!!",
                created_at="2023-01-01T00:00:00Z",
                updated_at="2023-01-01T00:00:00Z",
                context={"channel_id": "test_channel"}
            )
            
            thought_item = ProcessingQueueItem.from_thought(thought)
            
            # Test evaluation
            result = await dsdma.evaluate_thought(thought_item, {})
            
            # Verify result structure
            assert result.score == 0.8
            assert result.recommended_action == "none"
            assert isinstance(result.flags, list)
            assert result.reasoning == "Test reasoning"
            
        finally:
            # Restore original method
            ciris_engine.dma.dsdma_base.BaseDSDMA.evaluate_thought = original_evaluate
    
    @pytest.mark.asyncio
    async def test_evaluate_thought_low_score_recommendations(self):
        """Test that low scores trigger appropriate recommendations"""
        mock_registry = Mock(spec=ServiceRegistry)
        
        # Create DSDMA instance  
        dsdma = ModerationDSDMA(service_registry=mock_registry)
        
        # Mock the parent evaluate_thought method to return low score result
        from ciris_engine.schemas.dma_results_v1 import DSDMAResult
        async def mock_parent_evaluate_thought(self, thought_item, context):
            return DSDMAResult(
                domain="discord_moderation",
                score=0.15,  # Low score
                recommended_action="",  # No recommendation initially
                flags=[],
                reasoning="Low alignment"
            )
        
        # Patch the super().evaluate_thought call
        import ciris_engine.dma.dsdma_base
        original_evaluate = ciris_engine.dma.dsdma_base.BaseDSDMA.evaluate_thought
        ciris_engine.dma.dsdma_base.BaseDSDMA.evaluate_thought = mock_parent_evaluate_thought
        
        try:
            # Create test thought
            thought = Thought(
                thought_id="test_thought",
                source_task_id="test_task",
                thought_type=ThoughtType.OBSERVATION,
                content="Problematic content",
                created_at="2023-01-01T00:00:00Z",
                updated_at="2023-01-01T00:00:00Z"
            )
            
            thought_item = ProcessingQueueItem.from_thought(thought)
            
            # Test evaluation
            result = await dsdma.evaluate_thought(thought_item, {})
            
            # Verify recommendation was added based on low score
            assert result.score == 0.15
            assert result.recommended_action == "timeout_consideration"
            
        finally:
            # Restore original method
            ciris_engine.dma.dsdma_base.BaseDSDMA.evaluate_thought = original_evaluate
    
    def test_repr(self):
        """Test string representation"""
        mock_registry = Mock(spec=ServiceRegistry)
        dsdma = ModerationDSDMA(
            domain_name="test_domain",
            service_registry=mock_registry,
            model_name="test_model"
        )
        
        repr_str = repr(dsdma)
        assert "ModerationDSDMA" in repr_str
        assert "test_domain" in repr_str
        assert "test_model" in repr_str