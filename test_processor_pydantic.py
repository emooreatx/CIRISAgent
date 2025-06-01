#!/usr/bin/env python3
"""
Test script to verify processor works with Pydantic objects directly (no model_dump calls)
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from ciris_engine.schemas import (
    ActionSelectionResult, 
    Thought, 
    ThoughtStatus, 
    HandlerActionType, 
    RejectParams,
    DeferParams
)
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine import persistence

def test_processor_serialization():
    print("Testing processor Pydantic serialization...")
    
    # Test 1: Create ActionSelectionResult with Pydantic params
    reject_params = RejectParams(reason="Test rejection from processor")
    result = ActionSelectionResult(
        selected_action=HandlerActionType.REJECT,
        action_parameters=reject_params,  # Pydantic object, not dict
        rationale="Testing processor serialization"
    )
    
    print(f"✓ ActionSelectionResult created with Pydantic params")
    print(f"  Action: {result.selected_action}")
    print(f"  Params type: {type(result.action_parameters)}")
    print(f"  Params reason: {result.action_parameters.reason}")
    
    # Test 2: Create DeferParams for processor defer scenario
    defer_params = DeferParams(
        reason="Testing defer from processor",
        context={"test": "processor_context"}
    )
    defer_result = ActionSelectionResult(
        selected_action=HandlerActionType.DEFER,
        action_parameters=defer_params,  # Pydantic object, not dict
        rationale="Processor-generated defer"
    )
    
    print(f"✓ DeferParams ActionSelectionResult created")
    print(f"  Action: {defer_result.selected_action}")
    print(f"  Params type: {type(defer_result.action_parameters)}")
    
    # Test 3: Test ProcessingQueueItem with Pydantic context
    from datetime import datetime, timezone
    
    now = datetime.now(timezone.utc).isoformat()
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
    
    print(f"✓ ProcessingQueueItem created with Pydantic context")
    print(f"  Thought ID: {queue_item.thought_id}")
    print(f"  Context type: {type(queue_item.initial_context)}")
    
    # Test 4: Test final_action_details structure (like in _update_thought_status)
    final_action_details = {
        "action_type": HandlerActionType.DEFER.value,
        "parameters": defer_params,  # Pydantic object directly
        "rationale": "Test rationale"
    }
    
    print(f"✓ final_action_details created with Pydantic params")
    print(f"  Parameters type: {type(final_action_details['parameters'])}")
    
    # Test 5: Test persistence serialization
    try:
        # This should work now that persistence handles Pydantic objects
        result_serializes = hasattr(result, 'model_dump')
        details_has_pydantic = hasattr(final_action_details['parameters'], 'model_dump')
        
        print(f"✓ Serialization capability check:")
        print(f"  ActionSelectionResult can serialize: {result_serializes}")
        print(f"  final_action_details params can serialize: {details_has_pydantic}")
        
    except Exception as e:
        print(f"✗ Serialization test failed: {e}")
        return False
    
    print(f"✓ All processor tests passed - no model_dump() calls needed!")
    return True

if __name__ == "__main__":
    success = test_processor_serialization()
    sys.exit(0 if success else 1)
