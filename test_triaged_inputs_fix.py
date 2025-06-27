#!/usr/bin/env python3
"""Test script to verify the triaged_inputs fix."""

import asyncio
from unittest.mock import MagicMock, AsyncMock
from ciris_engine.logic.processors.support.dma_orchestrator import DMAOrchestrator
from ciris_engine.logic.processors.support.processing_queue import ProcessingQueueItem, ThoughtContent
from ciris_engine.schemas.runtime.models import Thought, ThoughtType
from ciris_engine.schemas.runtime.system_context import ThoughtContext
from ciris_engine.schemas.processors.dma import InitialDMAResults

async def test_triaged_inputs_dict():
    """Test that run_action_selection accepts dict for triaged_inputs."""
    
    # Create mocks
    ethical_pdma = MagicMock()
    csdma = MagicMock()
    dsdma = None
    action_selection_pdma = AsyncMock()
    time_service = MagicMock()
    time_service.now = MagicMock(return_value=MagicMock(isoformat=lambda: "2025-06-26T00:00:00"))
    
    orchestrator = DMAOrchestrator(
        ethical_pdma_evaluator=ethical_pdma,
        csdma_evaluator=csdma,
        dsdma=dsdma,
        action_selection_pdma_evaluator=action_selection_pdma,
        time_service=time_service
    )
    
    # Create test data
    from datetime import datetime
    now = datetime.now().isoformat()
    
    thought = Thought(
        thought_id="test-thought-1",
        source_task_id="test-task-1",
        thought_type=ThoughtType.STANDARD,
        thought_depth=1,
        round_number=1,
        content="Test thought",
        created_at=now,
        updated_at=now
    )
    
    thought_item = ProcessingQueueItem(
        thought_id=thought.thought_id,
        source_task_id=thought.source_task_id,
        thought_type=thought.thought_type,
        content=ThoughtContent(text="Test thought")
    )
    
    # Add conscience feedback to thought_item
    thought_item.conscience_feedback = {
        "failed_action": "speak: 'dangerous response'",
        "failure_reason": "Response might cause harm",
        "retry_guidance": "Please provide a safer response"
    }
    
    processing_context = ThoughtContext(
        initial_task_context=MagicMock(),
        system_snapshot=MagicMock(channel_context={"channel_id": "test-channel"})
    )
    
    dma_results = InitialDMAResults()
    
    # Test with dict triaged_inputs
    triaged_dict = {"retry_with_guidance": True}
    
    # Mock the action selection evaluator
    from ciris_engine.schemas.dma.results import ActionSelectionDMAResult
    from ciris_engine.schemas.runtime.enums import HandlerActionType
    
    expected_result = ActionSelectionDMAResult(
        selected_action=HandlerActionType.SPEAK,
        action_parameters={"content": "Safe response"},
        rationale="Providing a safe response after conscience feedback"
    )
    
    action_selection_pdma.evaluate.return_value = expected_result
    
    # This should not raise TypeError anymore
    result = await orchestrator.run_action_selection(
        thought_item=thought_item,
        actual_thought=thought,
        processing_context=processing_context,
        dma_results=dma_results,
        profile_name="default",
        triaged_inputs=triaged_dict  # Passing dict instead of ActionSelectionContext
    )
    
    print("✅ Test passed! run_action_selection accepts dict for triaged_inputs")
    print(f"Result: {result}")
    
    # Verify conscience feedback was passed through
    call_args = action_selection_pdma.evaluate.call_args
    if call_args:
        input_data = call_args[1].get('input_data', {})
        if 'conscience_feedback' in input_data:
            print("✅ Conscience feedback was passed through to action selection")
            print(f"Conscience feedback: {input_data['conscience_feedback']}")
        else:
            print("⚠️  Conscience feedback was not passed through")

if __name__ == "__main__":
    asyncio.run(test_triaged_inputs_dict())