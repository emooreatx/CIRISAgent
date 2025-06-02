"""
Test that persistence layer handles Pydantic objects correctly.
"""
import pytest
import tempfile
import os
import json
from datetime import datetime, timezone

from ciris_engine.persistence.db import initialize_database
from ciris_engine.persistence.models.thoughts import (
    update_thought_status,
    add_thought,
    get_thought_by_id,
)
from ciris_engine.persistence.models.tasks import add_task
from ciris_engine.schemas import (
    Thought, Task, ActionSelectionResult, RejectParams, DeferParams,
    ThoughtStatus, TaskStatus, HandlerActionType
)


class TestPersistencePydanticHandling:
    """Test that persistence layer correctly handles Pydantic objects without requiring manual serialization."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        # Initialize database
        initialize_database(db_path=db_path)
        
        yield db_path
        
        # Clean up
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    def sample_task_and_thought(self, temp_db):
        """Create sample task and thought for testing."""
        now = datetime.now(timezone.utc).isoformat()
        
        # Create test task
        task = Task(
            task_id="test-task-1",
            status=TaskStatus.ACTIVE,
            description="Test task for persistence",
            created_at=now,
            updated_at=now
        )
        add_task(task, db_path=temp_db)
        
        # Create test thought
        thought = Thought(
            thought_id="test-thought-1",
            source_task_id="test-task-1",
            thought_type="observation",
            status=ThoughtStatus.PENDING,
            content="Test thought content",
            created_at=now,
            updated_at=now,
            round_number=1
        )
        add_thought(thought, db_path=temp_db)
        
        return task, thought
    
    def test_update_thought_status_with_action_selection_result(self, temp_db, sample_task_and_thought):
        """Test updating thought status with ActionSelectionResult object."""
        task, thought = sample_task_and_thought
        
        # Create ActionSelectionResult with RejectParams
        reject_params = RejectParams(reason="Test rejection reason")
        action_result = ActionSelectionResult(
            selected_action=HandlerActionType.REJECT,
            action_parameters=reject_params,
            rationale="Testing rejection flow",
            confidence=0.95
        )
        
        # Pass ActionSelectionResult directly to update_thought_status
        success = update_thought_status(
            thought_id="test-thought-1",
            status=ThoughtStatus.FAILED,
            final_action=action_result,
            db_path=temp_db
        )
        
        assert success, "Failed to update thought status"
        
        # Verify the data was stored correctly
        retrieved_thought = get_thought_by_id("test-thought-1", db_path=temp_db)
        assert retrieved_thought is not None, "Failed to retrieve thought"
        assert retrieved_thought.status == ThoughtStatus.FAILED, "Status not updated correctly"
        
        # Check that final_action was serialized properly
        if hasattr(retrieved_thought, 'final_action') and retrieved_thought.final_action:
            final_action_data = json.loads(retrieved_thought.final_action) if isinstance(retrieved_thought.final_action, str) else retrieved_thought.final_action
            assert final_action_data['selected_action'] == HandlerActionType.REJECT.value
            assert final_action_data['rationale'] == "Testing rejection flow"
            assert final_action_data['confidence'] == 0.95
            
            # Check that nested Pydantic parameters were serialized correctly
            assert 'action_parameters' in final_action_data
            assert final_action_data['action_parameters']['reason'] == "Test rejection reason"
    
    def test_update_thought_status_with_plain_dict(self, temp_db, sample_task_and_thought):
        """Test updating thought status with plain dictionary."""
        task, thought = sample_task_and_thought
        
        # Create plain dict action
        plain_dict_action = {
            "action_type": "test",
            "parameters": {"key": "value"},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        success = update_thought_status(
            thought_id="test-thought-1",
            status=ThoughtStatus.COMPLETED,
            final_action=plain_dict_action,
            db_path=temp_db
        )
        
        assert success, "Failed to update thought status with dict"
        
        # Verify the data was stored correctly
        retrieved_thought = get_thought_by_id("test-thought-1", db_path=temp_db)
        assert retrieved_thought is not None
        assert retrieved_thought.status == ThoughtStatus.COMPLETED
        
        # Check that dict was stored properly
        if hasattr(retrieved_thought, 'final_action') and retrieved_thought.final_action:
            final_action_data = json.loads(retrieved_thought.final_action) if isinstance(retrieved_thought.final_action, str) else retrieved_thought.final_action
            assert final_action_data['action_type'] == "test"
            assert final_action_data['parameters']['key'] == "value"
    
    def test_persistence_handles_nested_pydantic_objects(self, temp_db, sample_task_and_thought):
        """Test that persistence correctly handles nested Pydantic objects."""
        task, thought = sample_task_and_thought
        
        # Create complex ActionSelectionResult with nested Pydantic parameters
        defer_params = DeferParams(
            reason="Complex defer scenario",
            context={"nested": {"data": "value"}, "count": 42}
        )
        
        action_result = ActionSelectionResult(
            selected_action=HandlerActionType.DEFER,
            action_parameters=defer_params,
            rationale="Testing complex nested serialization"
        )
        
        success = update_thought_status(
            thought_id="test-thought-1",
            status=ThoughtStatus.DEFERRED,
            final_action=action_result,
            db_path=temp_db
        )
        
        assert success
        
        # Verify complex nested data was preserved
        retrieved_thought = get_thought_by_id("test-thought-1", db_path=temp_db)
        assert retrieved_thought.status == ThoughtStatus.DEFERRED
        
        if hasattr(retrieved_thought, 'final_action') and retrieved_thought.final_action:
            final_action_data = json.loads(retrieved_thought.final_action) if isinstance(retrieved_thought.final_action, str) else retrieved_thought.final_action
            
            # Check top-level data
            assert final_action_data['selected_action'] == HandlerActionType.DEFER.value
            assert final_action_data['rationale'] == "Testing complex nested serialization"
            
            # Check nested parameter data
            params = final_action_data['action_parameters']
            assert params['reason'] == "Complex defer scenario"
            assert params['context']['nested']['data'] == "value"
            assert params['context']['count'] == 42
