"""
Test processor components work with Pydantic objects directly (no model_dump calls)
"""
import pytest
from datetime import datetime, timezone

from ciris_engine.schemas import (
    ActionSelectionResult, 
    Thought, 
    ThoughtStatus, 
    HandlerActionType, 
    RejectParams,
    DeferParams
)
from ciris_engine.processor.processing_queue import ProcessingQueueItem


class TestProcessorPydanticSerialization:
    """Test that processor components handle Pydantic objects correctly without manual serialization."""
    
    def test_action_selection_result_with_pydantic_params(self):
        """Test creating ActionSelectionResult with Pydantic parameters."""
        reject_params = RejectParams(reason="Test rejection from processor")
        result = ActionSelectionResult(
            selected_action=HandlerActionType.REJECT,
            action_parameters=reject_params,  # Pydantic object, not dict
            rationale="Testing processor serialization"
        )
        
        assert result.selected_action == HandlerActionType.REJECT
        assert isinstance(result.action_parameters, RejectParams)
        assert result.action_parameters.reason == "Test rejection from processor"
        assert result.rationale == "Testing processor serialization"
    
    def test_defer_params_action_selection_result(self):
        """Test creating ActionSelectionResult with DeferParams for processor defer scenario."""
        defer_params = DeferParams(
            reason="Testing defer from processor",
            context={"test": "processor_context"}
        )
        defer_result = ActionSelectionResult(
            selected_action=HandlerActionType.DEFER,
            action_parameters=defer_params,  # Pydantic object, not dict
            rationale="Processor-generated defer"
        )
        
        assert defer_result.selected_action == HandlerActionType.DEFER
        assert isinstance(defer_result.action_parameters, DeferParams)
        assert defer_result.action_parameters.reason == "Testing defer from processor"
        assert defer_result.action_parameters.context == {"test": "processor_context"}
    
    def test_processing_queue_item_with_pydantic_context(self):
        """Test ProcessingQueueItem creation with Pydantic objects in context."""
        now = datetime.now(timezone.utc).isoformat()
        reject_params = RejectParams(reason="Test rejection")
        defer_params = DeferParams(reason="Test defer", context={"defer": "context"})
        
        thought = Thought(
            thought_id="proc-test-123",
            source_task_id="proc-task-456",
            thought_type="human_interaction",
            status=ThoughtStatus.PENDING,
            created_at=now,
            updated_at=now,
            round_number=1,
            content="Testing processor thought",
            context={"processor_test": True, "params": reject_params}  # Mix of dict and Pydantic
        )
        
        queue_item = ProcessingQueueItem.from_thought(
            thought_instance=thought,
            initial_ctx={"queue_context": defer_params}  # Pydantic object in context
        )
        
        assert queue_item.thought_id == "proc-test-123"
        assert isinstance(queue_item.initial_context, dict)
        assert "queue_context" in queue_item.initial_context
        assert isinstance(queue_item.initial_context["queue_context"], DeferParams)
    
    def test_final_action_details_with_pydantic_params(self):
        """Test final_action_details structure like in _update_thought_status."""
        defer_params = DeferParams(reason="Test defer", context={"test": "context"})
        
        final_action_details = {
            "action_type": HandlerActionType.DEFER.value,
            "parameters": defer_params,  # Pydantic object directly
            "rationale": "Test rationale"
        }
        
        assert final_action_details["action_type"] == "defer"
        assert isinstance(final_action_details["parameters"], DeferParams)
        assert final_action_details["parameters"].reason == "Test defer"
        assert final_action_details["rationale"] == "Test rationale"
    
    def test_serialization_capability(self):
        """Test that objects have serialization capability when needed."""
        reject_params = RejectParams(reason="Test rejection")
        result = ActionSelectionResult(
            selected_action=HandlerActionType.REJECT,
            action_parameters=reject_params,
            rationale="Test rationale"
        )
        
        defer_params = DeferParams(reason="Test defer")
        final_action_details = {
            "action_type": HandlerActionType.DEFER.value,
            "parameters": defer_params,
            "rationale": "Test rationale"
        }
        
        # Both should have model_dump capability for serialization
        assert hasattr(result, 'model_dump')
        assert hasattr(final_action_details['parameters'], 'model_dump')
        
        # Test actual serialization works
        result_dict = result.model_dump()
        assert result_dict['selected_action'] == 'reject'
        assert result_dict['rationale'] == 'Test rationale'
        
        params_dict = defer_params.model_dump()
        assert params_dict['reason'] == 'Test defer'
