#!/usr/bin/env python3
"""
Test that Task persistence handles retry_count and outcome fields correctly.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from ciris_engine.logic.persistence.utils import map_row_to_task
from ciris_engine.schemas.runtime.enums import TaskStatus


def test_task_persistence_with_retry_count():
    """Test that retry_count is properly filtered out during mapping."""
    
    # Simulate a database row with retry_count
    class MockRow:
        def __init__(self, data):
            self._data = data
        
        def __getitem__(self, key):
            return self._data[key]
        
        def get(self, key, default=None):
            return self._data.get(key, default)
        
        def keys(self):
            return self._data.keys()
            
        def __iter__(self):
            return iter(self._data)
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Test case 1: Row with retry_count and empty outcome
    row_data = {
        "task_id": "TEST_TASK_1",
        "channel_id": "test_channel",  # Required field
        "description": "Test task",
        "status": "active",
        "priority": 1,
        "created_at": now,
        "updated_at": now,
        "parent_task_id": None,
        "context_json": None,
        "outcome_json": "{}",
        "retry_count": 0  # This should be filtered out
    }
    
    row = MockRow(row_data)
    task = map_row_to_task(row)
    
    # Verify retry_count was filtered out
    assert not hasattr(task, 'retry_count'), "retry_count should not exist on Task object"
    
    # Verify outcome is None for empty dict
    assert task.outcome is None, f"Expected outcome=None for empty dict, got {task.outcome}"
    
    # Verify other fields
    assert task.task_id == "TEST_TASK_1"
    assert task.status == TaskStatus.ACTIVE
    
    print("✓ Test 1 passed: retry_count filtered, empty outcome handled")
    
    # Test case 2: Row with valid outcome data
    outcome_data = {
        "status": "success",
        "summary": "Task completed successfully",
        "actions_taken": ["action1", "action2"],
        "memories_created": [],
        "errors": []
    }
    
    row_data["outcome_json"] = json.dumps(outcome_data)
    row = MockRow(row_data)
    task = map_row_to_task(row)
    
    # Verify outcome is properly parsed
    assert task.outcome is not None, "Outcome should be parsed for valid data"
    assert task.outcome.status == "success"
    assert task.outcome.summary == "Task completed successfully"
    assert len(task.outcome.actions_taken) == 2
    
    print("✓ Test 2 passed: Valid outcome properly parsed")
    
    # Test case 3: Row with null outcome_json
    row_data["outcome_json"] = None
    row = MockRow(row_data)
    task = map_row_to_task(row)
    
    assert task.outcome is None, "Outcome should be None for null outcome_json"
    
    print("✓ Test 3 passed: Null outcome handled")
    
    # Test case 4: Valid context data
    context_data = {
        "channel_id": "test-channel",
        "user_id": "test-user",
        "correlation_id": "test-correlation",
        "parent_task_id": None
    }
    
    row_data["context_json"] = json.dumps(context_data)
    row = MockRow(row_data)
    task = map_row_to_task(row)
    
    assert task.context is not None
    assert task.context.channel_id == "test-channel"
    assert task.context.user_id == "test-user"
    
    print("✓ Test 4 passed: Context properly parsed")
    
    print("\n✅ All Task persistence tests passed!")
    print("\nThe fixes handle:")
    print("  - Filtering out retry_count column")
    print("  - Converting empty outcome dicts to None")
    print("  - Properly validating TaskOutcome when data exists")
    print("  - Maintaining backward compatibility")


if __name__ == "__main__":
    test_task_persistence_with_retry_count()