"""
Comprehensive test suite for all CIRIS schema validation.

Tests schema structure, validation rules, and serialization/deserialization
for all schemas used in the CIRIS engine.
"""

import pytest
from datetime import datetime
from typing import Dict, Any
from pydantic import ValidationError

# Import all schemas
from ciris_engine.schemas.foundational_schemas_v1 import (
    IncomingMessage, 
    DiscordMessage,
    ObservationSourceType,
    FetchedMessage,
    ResourceUsage
)
from ciris_engine.schemas.action_params_v1 import (
    ObserveParams,
    SpeakParams,
    ToolParams,
    RecallParams,
    MemorizeParams,
    PonderParams,
    ForgetParams,
    DeferParams,
    RejectParams
)
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, GraphScope
from ciris_engine.schemas.dma_results_v1 import (
    ActionSelectionResult,
    EthicalDMAResult,
    CSDMAResult,
    DSDMAResult
)
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.memory_schemas_v1 import (
    MemoryOpResult,
    MemoryOpStatus,
    MemoryOpAction
)
from ciris_engine.schemas.context_schemas_v1 import (
    TaskContext,
    ThoughtContext,
    SystemSnapshot
)


class TestFoundationalSchemas:
    """Test foundational schemas that form the base of communication."""
    
    def test_incoming_message_required_fields(self):
        """Test IncomingMessage requires essential fields."""
        with pytest.raises(ValidationError):
            IncomingMessage()
        
        # Should work with required fields
        msg = IncomingMessage(
            message_id="msg123",
            author_id="user123",
            author_name="testuser",
            content="Hello",
            destination_id="dest123"
        )
        assert msg.content == "Hello"
        assert msg.author_id == "user123"
    
    def test_incoming_message_serialization(self):
        """Test IncomingMessage serialization round trip."""
        msg = IncomingMessage(
            message_id="msg456",
            author_id="user456",
            author_name="testuser2",
            content="Test message",
            timestamp="2024-01-01T12:00:00Z",
            destination_id="dest456"
        )
        
        # Serialize to dict and back
        data = msg.model_dump()
        reconstructed = IncomingMessage.model_validate(data)
        
        assert reconstructed.content == msg.content
        assert reconstructed.author_id == msg.author_id
        assert reconstructed.timestamp == msg.timestamp
    
    def test_discord_message_validation(self):
        """Test DiscordMessage validation rules."""
        # Valid Discord message
        msg = DiscordMessage(
            message_id="msg789",
            author_id="user789",
            author_name="discorduser",
            content="Discord message",
            channel_id="channel123",
            is_bot=False,
            is_dm=True
        )
        assert msg.content == "Discord message"
        assert msg.channel_id == "channel123"
        assert msg.is_dm is True
    
    def test_observation_source_type_enum(self):
        """Test ObservationSourceType enum values."""
        # Valid enum values
        assert ObservationSourceType.CHAT_MESSAGE == "chat_message"
        assert ObservationSourceType.USER_REQUEST == "user_request"  # type: ignore[unreachable]
        assert ObservationSourceType.AGENT_MESSAGE == "agent_message"
        
        # Should accept string values
        source = ObservationSourceType("chat_message")
        assert source == ObservationSourceType.CHAT_MESSAGE
    
    def test_fetched_message_schema(self):
        """Test FetchedMessage schema for communication protocol."""
        msg = FetchedMessage(
            content="Fetched content",
            author_id="user999",
            timestamp="2024-01-01T15:30:00Z",
            message_id="msg123"
        )
        
        assert msg.content == "Fetched content"
        assert msg.message_id == "msg123"
        
        # Test minimal message
        minimal_msg = FetchedMessage()
        assert minimal_msg.content is None
        assert minimal_msg.is_bot is False
    
    def test_resource_usage_schema(self):
        """Test ResourceUsage schema for tracking costs and environmental impact."""
        usage = ResourceUsage(
            tokens_used=150,
            cost_cents=0.2,
            energy_kwh=0.5
        )
        
        assert usage.tokens_used == 150
        assert usage.cost_cents == 0.2
        assert usage.energy_kwh == 0.5
        
        # Test minimal usage
        minimal_usage = ResourceUsage()
        assert minimal_usage.tokens_used == 0
        assert minimal_usage.cost_cents == 0.0  # Default value


class TestActionParamsSchemas:
    """Test action parameter schemas for consistent structure."""
    
    def test_observe_params(self):
        """Test ObserveParams schema."""
        params = ObserveParams(
            channel_id="channel123",
            active=True,
            context={"key": "value"}
        )
        
        assert params.channel_id == "channel123"
        assert params.active is True
        assert params.context["key"] == "value"
        
        # Test serialization
        data = params.model_dump()
        reconstructed = ObserveParams.model_validate(data)
        assert reconstructed.channel_id == params.channel_id
    
    def test_speak_params(self):
        """Test SpeakParams schema."""
        params = SpeakParams(
            content="Hello world",
            channel_id="channel123"
        )
        
        assert params.content == "Hello world"
        assert params.channel_id == "channel123"
        
        # Test extra fields forbidden
        with pytest.raises(ValidationError):
            SpeakParams.model_validate({
                "content": "Hello",
                "channel_id": "channel123", 
                "invalid_field": "should_fail"
            })
    
    def test_tool_params(self):
        """Test ToolParams schema with renamed parameters field."""
        params = ToolParams(
            name="search_web",
            parameters={"query": "CIRIS agent", "limit": 10}
        )
        
        assert params.name == "search_web"
        assert params.parameters["query"] == "CIRIS agent"
        assert params.parameters["limit"] == 10
    
    def test_recall_params(self):
        """Test RecallParams schema."""
        from ciris_engine.schemas.graph_schemas_v1 import NodeType
        
        node = GraphNode(
            id="test_node",
            type=NodeType.CONCEPT,
            scope=GraphScope.LOCAL,
            attributes={"query": "memory search"}
        )
        
        params = RecallParams(node=node)
        
        assert params.node.id == "test_node"
        assert params.node.type == NodeType.CONCEPT
        assert params.scope == GraphScope.LOCAL
    
    def test_memorize_params(self):
        """Test MemorizeParams schema."""
        from ciris_engine.schemas.graph_schemas_v1 import NodeType
        
        node = GraphNode(
            id="memory_node",
            type=NodeType.CONCEPT,
            scope=GraphScope.IDENTITY,
            attributes={"content": "Important fact to remember", "type": "fact"}
        )
        
        params = MemorizeParams(node=node)
        
        assert params.node.id == "memory_node"
        assert params.node.attributes["content"] == "Important fact to remember"
        assert params.scope == GraphScope.IDENTITY
    
    def test_all_action_params_forbid_extra(self):
        """Test that all action parameter schemas forbid extra fields."""
        param_classes = [
            ObserveParams, SpeakParams, ToolParams, RecallParams,
            MemorizeParams, PonderParams, ForgetParams, 
            DeferParams, RejectParams
        ]
        
        for param_class in param_classes:
            config = getattr(param_class, 'model_config', None)
            if config:
                assert config.get('extra') == 'forbid', f"{param_class.__name__} should forbid extra fields"


class TestDMAResultSchemas:
    """Test Decision Making Algorithm result schemas."""
    
    def test_action_selection_result(self):
        """Test ActionSelectionResult schema."""
        result = ActionSelectionResult(
            selected_action=HandlerActionType.SPEAK,
            action_parameters={"content": "Hello", "channel_id": "123"},
            rationale="User asked a question",
            confidence=0.95
        )
        
        assert result.selected_action == HandlerActionType.SPEAK
        assert result.rationale == "User asked a question"
        assert result.confidence == 0.95
        
        # Test with resource usage
        usage = ResourceUsage(
            tokens_used=75,
            cost_cents=0.001 * 100,  # Convert to cents
            energy_kwh=0.25
        )
        
        result_with_usage = ActionSelectionResult(
            selected_action=HandlerActionType.TOOL,
            action_parameters={"name": "search", "parameters": {}},
            rationale="Need to search for information",
            confidence=0.88,
            resource_usage=usage
        )
        
        assert result_with_usage.resource_usage.tokens_used == 75
        assert result_with_usage.resource_usage.cost_cents == 0.1
    
    def test_ethical_dma_result(self):
        """Test EthicalDMAResult schema."""
        result = EthicalDMAResult(
            alignment_check={"beneficence": True, "non_maleficence": True},
            decision="approve",
            rationale="Gathering more information aligns with principles"
        )
        
        assert result.decision == "approve"
        assert result.alignment_check["beneficence"] is True
        assert result.alignment_check["non_maleficence"] is True
    
    def test_csdma_result(self):
        """Test CSDMAResult schema."""
        result = CSDMAResult(
            plausibility_score=0.87,
            flags=["user_history", "current_topic"],
            reasoning="Need to check memory"
        )
        
        assert result.plausibility_score == 0.87
        assert "user_history" in result.flags
        assert result.reasoning == "Need to check memory"
    
    def test_dsdma_result(self):
        """Test DSDMAResult schema with renamed score field."""
        result = DSDMAResult(
            domain="technical",
            score=0.82,
            flags=["complexity"],
            reasoning="Complex decision needed",
            recommended_action="ponder"
        )
        
        assert result.domain == "technical"
        assert result.score == 0.82
        assert result.recommended_action == "ponder"


class TestMemorySchemas:
    """Test memory-related schemas."""
    
    def test_memory_op_result(self):
        """Test MemoryOpResult schema."""
        result = MemoryOpResult(
            status=MemoryOpStatus.OK,
            reason="Memory stored successfully"
        )
        
        assert result.status == MemoryOpStatus.OK
        assert result.reason == "Memory stored successfully"
        
        # Test with data and error
        result_with_data = MemoryOpResult(
            status=MemoryOpStatus.DEFERRED,
            reason="Query needs review",
            data={"results": [{"id": "mem1", "content": "remembered fact"}]},
            error=None
        )
        
        assert result_with_data.status == MemoryOpStatus.DEFERRED
        assert result_with_data.data["results"][0]["content"] == "remembered fact"
    
    def test_memory_op_action_enum(self):
        """Test MemoryOpAction enum."""
        assert MemoryOpAction.MEMORIZE == "memorize"
        assert MemoryOpAction.RECALL == "recall"  # type: ignore[unreachable]
        assert MemoryOpAction.FORGET == "forget"
        
        # Test enum usage
        action = MemoryOpAction("memorize")
        assert action == MemoryOpAction.MEMORIZE


class TestContextSchemas:
    """Test context schemas."""
    
    def test_task_context(self):
        """Test TaskContext schema."""
        context = TaskContext(
            author_name="testuser",
            author_id="user123",
            channel_id="channel456",
            origin_service="discord"
        )
        
        assert context.author_name == "testuser"
        assert context.author_id == "user123"
        assert context.channel_id == "channel456"
        assert context.origin_service == "discord"
        
        # Test dictionary-style access
        assert "author_name" in context
        assert context.get("author_name") == "testuser"
        assert context["author_id"] == "user123"
    
    def test_system_snapshot(self):
        """Test SystemSnapshot schema."""
        snapshot = SystemSnapshot(
            system_counts={"tasks": 5, "thoughts": 3},
            channel_id="test_channel"
        )
        
        assert snapshot.system_counts["tasks"] == 5
        assert snapshot.system_counts["thoughts"] == 3
        assert snapshot.channel_id == "test_channel"
    
    def test_thought_context(self):
        """Test ThoughtContext schema."""
        context = ThoughtContext(
            identity_context="I am a helpful assistant"
        )
        
        assert context.identity_context == "I am a helpful assistant"
        assert isinstance(context.system_snapshot, SystemSnapshot)
        
        # Test dictionary-style access
        assert "identity_context" in context
        assert context.get("identity_context") == "I am a helpful assistant"


class TestSchemaIntegration:
    """Test schema integration and consistency."""
    
    def test_timestamp_format_consistency(self):
        """Test that all timestamp fields use ISO8601 string format."""
        # Test IncomingMessage timestamp
        msg = IncomingMessage(
            message_id="msg123",
            author_id="user123",
            author_name="testuser",
            content="Test",
            timestamp="2024-01-01T12:00:00Z",
            destination_id="dest123"
        )
        assert isinstance(msg.timestamp, str)
        
        # Test FetchedMessage timestamp
        fetched = FetchedMessage(
            content="Fetched",
            author_id="user456",
            timestamp="2024-01-01T13:00:00Z",
            message_id="msg123"
        )
        assert isinstance(fetched.timestamp, str)
    
    def test_content_field_consistency(self):
        """Test that content fields are consistently named."""
        # All these should have 'content' field, not 'message_content'
        incoming = IncomingMessage(
            message_id="msg123",
            author_id="user123",
            author_name="testuser",
            content="Hello",
            timestamp="2024-01-01T12:00:00Z",
            destination_id="dest123"
        )
        
        speak_params = SpeakParams(
            content="Speech",
            channel_id="dest123"
        )
        
        # All should have content field
        for obj in [incoming, speak_params]:
            assert hasattr(obj, 'content')
            assert obj.content is not None
    
    def test_plausibility_score_consistency(self):
        """Test that plausibility scoring is consistently named."""
        # This test ensures we don't have variations like 
        # common_sense_plausibility_score vs plausibility_score
        
        # ActionSelectionResult should have confidence, not plausibility_score
        result = ActionSelectionResult(
            selected_action=HandlerActionType.SPEAK,
            action_parameters={"content": "test"},
            rationale="Test",
            confidence=0.95
        )
        
        assert hasattr(result, 'confidence')
        assert not hasattr(result, 'plausibility_score')
        assert not hasattr(result, 'common_sense_plausibility_score')
    
    def test_resource_usage_integration(self):
        """Test ResourceUsage integration across DMA results."""
        usage = ResourceUsage(
            tokens_used=150,
            cost_cents=0.2,
            energy_kwh=0.5
        )
        
        # All DMA results should accept resource_usage
        action_result = ActionSelectionResult(
            selected_action=HandlerActionType.TOOL,
            action_parameters={"name": "search"},
            rationale="Using external API",
            confidence=0.89,
            resource_usage=usage
        )
        
        ethical_result = EthicalDMAResult(
            alignment_check={"beneficence": True},
            decision="approve",
            rationale="Ethical response needed",
            resource_usage=usage
        )
        
        assert action_result.resource_usage.tokens_used == 150
        assert ethical_result.resource_usage.cost_cents == 0.2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])