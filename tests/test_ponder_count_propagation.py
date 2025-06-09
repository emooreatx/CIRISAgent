"""
Test suite for ponder count propagation across action handlers.

This test verifies that ponder_count is properly incremented when handlers
create follow-up thoughts, ensuring thoughts are tracked correctly through
multiple processing rounds without terminal states (DEFER, REJECT, TASK_COMPLETE).
"""

import pytest
import uuid
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from ciris_engine.schemas.agent_core_schemas_v1 import Thought, Task
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, TaskStatus, HandlerActionType
from ciris_engine.schemas.context_schemas_v1 import ThoughtContext
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.action_params_v1 import PonderParams, RecallParams, MemorizeParams
from ciris_engine.action_handlers.helpers import create_follow_up_thought
from ciris_engine.action_handlers.ponder_handler import PonderHandler
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies


class TestPonderCountPropagation:
    """Test ponder count propagation across different scenarios."""
    
    @pytest.fixture
    def sample_task(self):
        """Create a sample task for testing."""
        return Task(
            task_id=str(uuid.uuid4()),
            description="Test task for ponder count verification",
            status=TaskStatus.ACTIVE,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            channel_id="test_channel"
        )
    
    @pytest.fixture  
    def base_thought(self, sample_task):
        """Create a base thought with ponder_count=0."""
        return Thought(
            thought_id=str(uuid.uuid4()),
            content="Initial thought content",
            source_task_id=sample_task.task_id,
            status=ThoughtStatus.PENDING,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            ponder_count=0,
            context=ThoughtContext()
        )
    
    @pytest.fixture
    def pondered_thought(self, sample_task):
        """Create a thought that has been pondered once (ponder_count=1)."""
        return Thought(
            thought_id=str(uuid.uuid4()),
            content="Pondered thought content",
            source_task_id=sample_task.task_id,
            status=ThoughtStatus.PENDING,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            ponder_count=1,
            ponder_notes=["Initial ponder question"],
            context=ThoughtContext()
        )
    
    @pytest.fixture
    def heavily_pondered_thought(self, sample_task):
        """Create a thought that has been pondered multiple times (ponder_count=3)."""
        return Thought(
            thought_id=str(uuid.uuid4()),
            content="Heavily pondered thought content", 
            source_task_id=sample_task.task_id,
            status=ThoughtStatus.PENDING,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            ponder_count=3,
            ponder_notes=["Question 1", "Question 2", "Question 3"],
            context=ThoughtContext()
        )
    
    def test_create_follow_up_thought_increments_ponder_count(self, base_thought):
        """Test that create_follow_up_thought properly increments ponder_count."""
        follow_up = create_follow_up_thought(
            parent=base_thought,
            content="Follow-up thought content"
        )
        
        # Follow-up should have parent's ponder_count + 1
        assert follow_up.ponder_count == base_thought.ponder_count + 1
        assert follow_up.ponder_count == 1
        
        # Verify other properties are correctly set
        assert follow_up.source_task_id == base_thought.source_task_id
        assert follow_up.parent_thought_id == base_thought.thought_id
        assert follow_up.content == "Follow-up thought content"
    
    def test_create_follow_up_from_pondered_thought(self, pondered_thought):
        """Test follow-up creation from already pondered thought."""
        follow_up = create_follow_up_thought(
            parent=pondered_thought,
            content="Second follow-up thought"
        )
        
        # Should increment from parent's count
        assert follow_up.ponder_count == pondered_thought.ponder_count + 1
        assert follow_up.ponder_count == 2
    
    def test_create_follow_up_chain_maintains_count(self, base_thought):
        """Test that a chain of follow-ups maintains proper ponder count progression."""
        # Create first follow-up (ponder_count should be 1)
        first_follow_up = create_follow_up_thought(
            parent=base_thought,
            content="First follow-up"
        )
        assert first_follow_up.ponder_count == 1
        
        # Create second follow-up from first (ponder_count should be 2)
        second_follow_up = create_follow_up_thought(
            parent=first_follow_up,
            content="Second follow-up"
        )
        assert second_follow_up.ponder_count == 2
        
        # Create third follow-up from second (ponder_count should be 3)
        third_follow_up = create_follow_up_thought(
            parent=second_follow_up,
            content="Third follow-up"
        )
        assert third_follow_up.ponder_count == 3
    
    @patch('ciris_engine.action_handlers.ponder_handler.persistence')
    def test_ponder_handler_creates_correct_follow_up_count(self, mock_persistence, pondered_thought):
        """Test that PonderHandler creates follow-ups with correct ponder count."""
        # Mock dependencies with action_dispatcher
        mock_dependencies = Mock(spec=ActionHandlerDependencies)
        mock_action_dispatcher = Mock()
        mock_action_dispatcher.get_handler.return_value = None
        mock_dependencies.action_dispatcher = mock_action_dispatcher
        
        # Mock persistence calls
        mock_persistence.update_thought_status.return_value = True
        mock_persistence.get_task_by_id.return_value = Mock(description="Test task")
        mock_persistence.add_thought.return_value = None
        
        # Create PonderHandler
        ponder_handler = PonderHandler(mock_dependencies, max_rounds=5)
        
        # Create action result with ponder parameters
        ponder_result = ActionSelectionResult(
            selected_action=HandlerActionType.PONDER,
            action_parameters=PonderParams(
                questions=["Why did this fail guardrails?", "What's a better approach?"]
            ).model_dump(),
            rationale="Failed guardrails check",
            raw_llm_response=None
        )
        
        # Mock the handle method to capture the follow-up thought
        captured_thoughts = []
        def capture_add_thought(thought):
            captured_thoughts.append(thought)
        mock_persistence.add_thought.side_effect = capture_add_thought
        
        # Handle the ponder action
        import asyncio
        asyncio.run(ponder_handler.handle(ponder_result, pondered_thought, {}))
        
        # Verify follow-up thought was created with correct ponder count
        assert len(captured_thoughts) == 1
        follow_up_thought = captured_thoughts[0]
        assert follow_up_thought.ponder_count == pondered_thought.ponder_count + 1
        assert follow_up_thought.ponder_count == 2
    
    def test_ponder_handler_dynamic_content_generation(self, heavily_pondered_thought):
        """Test that PonderHandler generates appropriate content based on ponder count."""
        mock_dependencies = Mock(spec=ActionHandlerDependencies)
        ponder_handler = PonderHandler(mock_dependencies, max_rounds=5)
        
        # Test content generation for different ponder counts
        questions = ["Persistent issue", "Still failing"]
        
        # Test heavily pondered content (count=4 after increment)
        content = ponder_handler._generate_ponder_follow_up_content(
            "Test task", questions, 4, heavily_pondered_thought
        )
        
        # Should include guidance about multiple attempts and suggest alternatives
        assert "Multiple attempts (4)" in content
        assert "repeatedly blocked by guardrails" in content
        assert "defer to human oversight" in content
        assert "fundamentally different approach" in content
    
    def test_max_rounds_behavior_with_ponder_count(self, heavily_pondered_thought):
        """Test that max rounds are properly enforced based on ponder count."""
        mock_dependencies = Mock(spec=ActionHandlerDependencies)
        mock_action_dispatcher = Mock()
        mock_defer_handler = AsyncMock()
        mock_action_dispatcher.get_handler.return_value = mock_defer_handler
        mock_dependencies.action_dispatcher = mock_action_dispatcher
        
        # Set max rounds to 4, so a thought with ponder_count=3 should defer on next ponder
        ponder_handler = PonderHandler(mock_dependencies, max_rounds=4)
        
        ponder_result = ActionSelectionResult(
            selected_action=HandlerActionType.PONDER,
            action_parameters=PonderParams(questions=["Final attempt"]).model_dump(),
            rationale="Last chance",
            raw_llm_response=None
        )
        
        # Should trigger defer handler when max rounds reached
        import asyncio
        asyncio.run(ponder_handler.handle(ponder_result, heavily_pondered_thought, {}))
        
        # Verify defer handler was called
        mock_defer_handler.handle.assert_called_once()
        call_args = mock_defer_handler.handle.call_args
        defer_result, thought, context = call_args[0]
        
        # Verify defer result has correct action and reasoning
        assert defer_result.selected_action == HandlerActionType.DEFER
        assert "Maximum action rounds (4) reached" in defer_result.action_parameters['reason']
    
    @pytest.mark.parametrize("initial_count,expected_follow_up_count", [
        (0, 1),
        (1, 2), 
        (2, 3),
        (5, 6),
        (10, 11)
    ])
    def test_ponder_count_increment_edge_cases(self, sample_task, initial_count, expected_follow_up_count):
        """Test ponder count increment for various edge cases."""
        thought = Thought(
            thought_id=str(uuid.uuid4()),
            content="Test thought",
            source_task_id=sample_task.task_id,
            status=ThoughtStatus.PENDING,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            ponder_count=initial_count,
            context=ThoughtContext()
        )
        
        follow_up = create_follow_up_thought(
            parent=thought,
            content="Follow-up content"
        )
        
        assert follow_up.ponder_count == expected_follow_up_count


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
