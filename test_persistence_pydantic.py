#!/usr/bin/env python3
"""Test script to verify persistence layer handles Pydantic objects correctly."""

import tempfile
import os
from ciris_engine.persistence.db import initialize_database
from ciris_engine.persistence.models.thoughts import (
    update_thought_status,
    add_thought,
    get_thought_by_id,
)
from ciris_engine.persistence.models.tasks import add_task
from ciris_engine.schemas import (
    Thought, Task, ActionSelectionResult, RejectParams,
    ThoughtStatus, TaskStatus, HandlerActionType
)
from datetime import datetime, timezone
import json


def test_persistence_with_pydantic():
    """Test that persistence handles ActionSelectionResult objects properly."""
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Initialize database
        initialize_database(db_path=db_path)
        
        # Create test task
        now = datetime.now(timezone.utc).isoformat()
        task = Task(
            task_id="test-task-1",
            status=TaskStatus.ACTIVE,
            description="Test task for persistence",
            created_at=now,
            updated_at=now
        )
        add_task(task, db_path=db_path)
        
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
        add_thought(thought, db_path=db_path)
        
        # Create ActionSelectionResult with RejectParams
        reject_params = RejectParams(reason="Test rejection reason")
        action_result = ActionSelectionResult(
            selected_action=HandlerActionType.REJECT,
            action_parameters=reject_params,
            rationale="Testing rejection flow",
            confidence=0.95
        )
        
        # Test 1: Pass ActionSelectionResult directly to update_thought_status
        print("Test 1: Updating thought status with ActionSelectionResult object...")
        success = update_thought_status(
            thought_id="test-thought-1",
            status=ThoughtStatus.FAILED,
            final_action=action_result,
            db_path=db_path
        )
        assert success, "Failed to update thought status"
        print("✓ Successfully updated thought status with ActionSelectionResult")
        
        # Verify the data was stored correctly
        retrieved_thought = get_thought_by_id("test-thought-1", db_path=db_path)
        assert retrieved_thought is not None, "Failed to retrieve thought"
        assert retrieved_thought.status == ThoughtStatus.FAILED, "Status not updated correctly"
        
        # Check that final_action was serialized properly
        if hasattr(retrieved_thought, 'final_action') and retrieved_thought.final_action:
            final_action_data = json.loads(retrieved_thought.final_action) if isinstance(retrieved_thought.final_action, str) else retrieved_thought.final_action
            assert final_action_data['selected_action'] == HandlerActionType.REJECT.value
            assert final_action_data['rationale'] == "Testing rejection flow"
            assert final_action_data['confidence'] == 0.95
            print("✓ Final action data serialized and retrieved correctly")
        
        # Test 2: Pass a plain dict to update_thought_status
        print("\nTest 2: Updating thought status with plain dict...")
        plain_dict_action = {
            "action_type": "test",
            "parameters": {"key": "value"},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        success = update_thought_status(
            thought_id="test-thought-1",
            status=ThoughtStatus.COMPLETED,
            final_action=plain_dict_action,
            db_path=db_path
        )
        assert success, "Failed to update thought status with dict"
        print("✓ Successfully updated thought status with plain dict")
        
        print("\n🎉 All tests passed! Persistence layer correctly handles both Pydantic objects and dicts.")
        
    finally:
        # Clean up
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    test_persistence_with_pydantic()
