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
    
    def test_should_defer_to_human_escalation_triggers(self):
        """Test escalation trigger detection"""
        mock_registry = Mock(spec=ServiceRegistry)
        dsdma = ModerationDSDMA(service_registry=mock_registry)
        
        # Test escalation triggers
        assert dsdma._should_defer_to_human("I want to hurt myself", [])
        assert dsdma._should_defer_to_human("This is a complex interpersonal conflict", [])
        assert dsdma._should_defer_to_human("potential legal issues here", [])
        
        # Test normal content
        assert not dsdma._should_defer_to_human("Hello everyone!", [])
        assert not dsdma._should_defer_to_human("Can someone help me?", [])
    
    def test_should_defer_to_human_complexity_flags(self):
        """Test deferral based on complexity flags"""
        mock_registry = Mock(spec=ServiceRegistry)
        dsdma = ModerationDSDMA(service_registry=mock_registry)
        
        # Test complexity flags
        assert dsdma._should_defer_to_human("Normal message", ["complex_conflict"])
        assert dsdma._should_defer_to_human("Normal message", ["legal_concern"])
        assert dsdma._should_defer_to_human("Normal message", ["welfare_risk"])
        
        # Test normal flags
        assert not dsdma._should_defer_to_human("Normal message", ["spam"])
        assert not dsdma._should_defer_to_human("Normal message", ["new_user"])
    
    @pytest.mark.asyncio
    async def test_evaluate_thought_context_enrichment(self):
        """Test that evaluate_thought enriches context with moderation data"""
        mock_registry = Mock(spec=ServiceRegistry)
        
        # Mock the parent evaluate_thought method
        dsdma = ModerationDSDMA(service_registry=mock_registry)
        dsdma._get_llm_service = AsyncMock()
        
        # Create mock LLM service that returns a structured result
        mock_llm = AsyncMock()
        mock_llm.generate_structured_response = AsyncMock(return_value={
            "score": 0.8,
            "recommended_action": "none",
            "flags": [],
            "reasoning": "Test reasoning"
        })
        dsdma._get_llm_service.return_value = mock_llm
        
        # Create test thought
        thought = Thought(
            thought_id="test_thought",
            thought_type=ThoughtType.INCOMING_MESSAGE,
            content="Hello @everyone! THIS IS URGENT!!!",
            channel_id="test_channel",
            context={"channel_id": "test_channel"}
        )
        
        thought_item = ProcessingQueueItem(
            item_id="test_item",
            content=thought,
            priority=50
        )
        
        # Test evaluation
        result = await dsdma.evaluate_thought(thought_item, {})
        
        # Verify LLM was called
        assert mock_llm.generate_structured_response.called
        
        # Verify result structure
        assert result.score == 0.8
        assert result.recommended_action == "none"
        assert isinstance(result.flags, list)
        assert result.reasoning == "Test reasoning"
    
    @pytest.mark.asyncio
    async def test_evaluate_thought_low_score_recommendations(self):
        """Test that low scores trigger appropriate recommendations"""
        mock_registry = Mock(spec=ServiceRegistry)
        
        dsdma = ModerationDSDMA(service_registry=mock_registry)
        dsdma._get_llm_service = AsyncMock()
        
        # Mock LLM to return low score without recommendation
        mock_llm = AsyncMock()
        mock_llm.generate_structured_response = AsyncMock(return_value={
            "score": 0.15,  # Low score
            "recommended_action": "",  # No recommendation
            "flags": [],
            "reasoning": "Low alignment"
        })
        dsdma._get_llm_service.return_value = mock_llm
        
        # Create test thought
        thought = Thought(
            thought_id="test_thought",
            thought_type=ThoughtType.INCOMING_MESSAGE,
            content="Problematic content",
            channel_id="test_channel"
        )
        
        thought_item = ProcessingQueueItem(
            item_id="test_item",
            content=thought,
            priority=50
        )
        
        # Test evaluation
        result = await dsdma.evaluate_thought(thought_item, {})
        
        # Verify recommendation was added based on low score
        assert result.score == 0.15
        assert result.recommended_action == "timeout_consideration"
    
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