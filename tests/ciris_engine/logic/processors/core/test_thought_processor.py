"""Unit tests for ThoughtProcessor."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from ciris_engine.logic.processors.core.thought_processor import ThoughtProcessor
from ciris_engine.logic.processors.support.processing_queue import ProcessingQueue, ProcessingQueueItem
from ciris_engine.schemas.runtime.models import Task, Thought, ThoughtContext
from ciris_engine.schemas.runtime.enums import (
    TaskStatus, ThoughtStatus, ThoughtType, HandlerActionType
)
from ciris_engine.schemas.dma.decisions import ActionSelectionDecision
from ciris_engine.schemas.dma.results import ActionSelectionDMAResult


class TestThoughtProcessor:
    """Test cases for ThoughtProcessor."""
    
    @pytest.fixture
    def mock_time_service(self):
        """Create mock time service."""
        current_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        return Mock(
            now=Mock(return_value=current_time),
            now_iso=Mock(return_value=current_time.isoformat())
        )
    
    @pytest.fixture
    def mock_bus_manager(self):
        """Create mock bus manager."""
        mock_llm_bus = Mock()
        mock_llm_bus.select_action = AsyncMock(return_value=ActionSelectionDMAResult(
            selected_action=HandlerActionType.SPEAK,
            action_parameters={"content": "Test response"},
            rationale="Test rationale"
        ))
        
        mock_bus_manager = Mock()
        mock_bus_manager.llm_bus = mock_llm_bus
        mock_bus_manager.memory_bus = Mock()
        mock_bus_manager.wise_bus = Mock()
        
        return mock_bus_manager
    
    @pytest.fixture
    def mock_action_dispatcher(self):
        """Create mock action dispatcher."""
        dispatcher = Mock()
        dispatcher.can_handle = Mock(return_value=True)
        dispatcher.dispatch = AsyncMock(return_value=Mock(
            success=True,
            should_continue=True,
            error=None
        ))
        return dispatcher
    
    @pytest.fixture
    def mock_persistence(self):
        """Create mock persistence functions."""
        with patch('ciris_engine.logic.processors.core.thought_processor.persistence') as mock_persist:
            mock_persist.get_task_by_id = Mock(return_value=Mock(
                task_id="test_task",
                description="Test task",
                status=TaskStatus.ACTIVE
            ))
            mock_persist.add_thought = Mock()
            mock_persist.update_thought_status = Mock()
            mock_persist.update_task_status = Mock()
            yield mock_persist
    
    @pytest.fixture
    def thought_processor(
        self, 
        mock_time_service, 
        mock_bus_manager, 
        mock_action_dispatcher,
        mock_persistence
    ):
        """Create ThoughtProcessor instance."""
        processor = ThoughtProcessor(
            bus_manager=mock_bus_manager,
            action_dispatcher=mock_action_dispatcher,
            time_service=mock_time_service,
            max_thought_depth=5,
            max_thoughts_per_task=20
        )
        return processor
    
    def test_get_processing_queue(self, thought_processor):
        """Test getting the processing queue."""
        queue = thought_processor.get_processing_queue()
        assert isinstance(queue, ProcessingQueue)
        assert queue is thought_processor._processing_queue
    
    @pytest.mark.asyncio
    async def test_create_thought_from_task(self, thought_processor):
        """Test creating a thought from a task."""
        task = Task(
            task_id="test_task",
            channel_id="test_channel",
            description="Test task description",
            status=TaskStatus.ACTIVE,
            created_at=thought_processor.time_service.now_iso(),
            updated_at=thought_processor.time_service.now_iso()
        )
        
        thought = await thought_processor.create_thought_from_task(
            task=task,
            channel_id="test_channel",
            correlation_id="test_correlation"
        )
        
        assert thought.source_task_id == task.task_id
        assert thought.content == f"New task: {task.description}"
        assert thought.thought_type == ThoughtType.TASK_ANALYSIS
        assert thought.status == ThoughtStatus.PENDING
        assert thought.thought_depth == 0
    
    @pytest.mark.asyncio
    async def test_create_follow_up_thought(self, thought_processor):
        """Test creating a follow-up thought."""
        parent_thought = Thought(
            thought_id="parent_thought",
            content="Parent thought",
            source_task_id="test_task",
            status=ThoughtStatus.COMPLETED,
            created_at=thought_processor.time_service.now_iso(),
            updated_at=thought_processor.time_service.now_iso(),
            thought_depth=1
        )
        
        follow_up = await thought_processor.create_follow_up_thought(
            parent_thought=parent_thought,
            content="Follow-up content",
            thought_type=ThoughtType.REFLECTION
        )
        
        assert follow_up.parent_thought_id == parent_thought.thought_id
        assert follow_up.content == "Follow-up content"
        assert follow_up.thought_type == ThoughtType.REFLECTION
        assert follow_up.thought_depth == 2  # Parent depth + 1
    
    @pytest.mark.asyncio
    async def test_process_single_thought(self, thought_processor, mock_bus_manager):
        """Test processing a single thought."""
        thought = Thought(
            thought_id="test_thought",
            content="Test thought content",
            source_task_id="test_task",
            status=ThoughtStatus.PENDING,
            created_at=thought_processor.time_service.now_iso(),
            updated_at=thought_processor.time_service.now_iso(),
            thought_depth=0,
            context=ThoughtContext(
                task_id="test_task",
                correlation_id="test_correlation",
                round_number=1,
                depth=0
            )
        )
        
        # Add to queue
        thought_processor._processing_queue.enqueue(
            thought=thought,
            channel_id="test_channel",
            priority=5
        )
        
        # Process
        processed = await thought_processor.process_next_thought()
        
        assert processed is True
        mock_bus_manager.llm_bus.select_action.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_thought_with_error(self, thought_processor, mock_bus_manager):
        """Test processing thought that encounters an error."""
        # Make LLM bus raise error
        mock_bus_manager.llm_bus.select_action.side_effect = Exception("LLM error")
        
        thought = Thought(
            thought_id="test_thought",
            content="Test thought",
            source_task_id="test_task",
            status=ThoughtStatus.PENDING,
            created_at=thought_processor.time_service.now_iso(),
            updated_at=thought_processor.time_service.now_iso(),
            thought_depth=0,
            context=ThoughtContext(
                task_id="test_task",
                correlation_id="test_correlation",
                round_number=1,
                depth=0
            )
        )
        
        thought_processor._processing_queue.enqueue(
            thought=thought,
            channel_id="test_channel",
            priority=5
        )
        
        # Should handle error gracefully
        processed = await thought_processor.process_next_thought()
        
        assert processed is True
        # Thought should be marked as failed
        thought_processor._persistence.update_thought_status.assert_called_with(
            thought_id="test_thought",
            status=ThoughtStatus.FAILED,
            db_path=thought_processor._db_path
        )
    
    @pytest.mark.asyncio
    async def test_max_thought_depth_limit(self, thought_processor):
        """Test that thoughts exceeding max depth are rejected."""
        thought = Thought(
            thought_id="deep_thought",
            content="Very deep thought",
            source_task_id="test_task",
            status=ThoughtStatus.PENDING,
            created_at=thought_processor.time_service.now_iso(),
            updated_at=thought_processor.time_service.now_iso(),
            thought_depth=6  # Exceeds max of 5
        )
        
        with pytest.raises(ValueError) as exc_info:
            await thought_processor.create_follow_up_thought(
                parent_thought=thought,
                content="Too deep",
                thought_type=ThoughtType.REFLECTION
            )
        
        assert "max depth" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_process_multiple_thoughts(self, thought_processor):
        """Test processing multiple thoughts in sequence."""
        # Add multiple thoughts to queue
        for i in range(3):
            thought = Thought(
                thought_id=f"thought_{i}",
                content=f"Thought {i}",
                source_task_id="test_task",
                status=ThoughtStatus.PENDING,
                created_at=thought_processor.time_service.now_iso(),
                updated_at=thought_processor.time_service.now_iso(),
                thought_depth=0,
                context=ThoughtContext(
                    task_id="test_task",
                    correlation_id=f"correlation_{i}",
                    round_number=1,
                    depth=0
                )
            )
            
            thought_processor._processing_queue.enqueue(
                thought=thought,
                channel_id="test_channel",
                priority=5 - i  # Different priorities
            )
        
        # Process all
        count = 0
        while not thought_processor._processing_queue.is_empty():
            processed = await thought_processor.process_next_thought()
            if processed:
                count += 1
        
        assert count == 3
    
    @pytest.mark.asyncio
    async def test_handle_terminal_action(self, thought_processor, mock_bus_manager):
        """Test handling terminal actions like TASK_COMPLETE."""
        # Set LLM to return TASK_COMPLETE
        mock_bus_manager.llm_bus.select_action.return_value = ActionSelectionDMAResult(
            selected_action=HandlerActionType.TASK_COMPLETE,
            action_parameters={"outcome": "Task completed successfully"},
            rationale="Task is done"
        )
        
        thought = Thought(
            thought_id="final_thought",
            content="Final thought",
            source_task_id="test_task",
            status=ThoughtStatus.PENDING,
            created_at=thought_processor.time_service.now_iso(),
            updated_at=thought_processor.time_service.now_iso(),
            thought_depth=0,
            context=ThoughtContext(
                task_id="test_task",
                correlation_id="test_correlation",
                round_number=1,
                depth=0
            )
        )
        
        thought_processor._processing_queue.enqueue(
            thought=thought,
            channel_id="test_channel",
            priority=5
        )
        
        # Process
        await thought_processor.process_next_thought()
        
        # Task should be marked as completed
        thought_processor._persistence.update_task_status.assert_called_with(
            task_id="test_task",
            status=TaskStatus.COMPLETED,
            db_path=thought_processor._db_path
        )
    
    @pytest.mark.asyncio
    async def test_action_dispatch_failure(self, thought_processor, mock_action_dispatcher):
        """Test handling action dispatch failure."""
        # Make dispatcher fail
        mock_action_dispatcher.dispatch.return_value = Mock(
            success=False,
            error="Dispatch failed"
        )
        
        thought = Thought(
            thought_id="test_thought",
            content="Test thought",
            source_task_id="test_task",
            status=ThoughtStatus.PENDING,
            created_at=thought_processor.time_service.now_iso(),
            updated_at=thought_processor.time_service.now_iso(),
            thought_depth=0,
            context=ThoughtContext(
                task_id="test_task",
                correlation_id="test_correlation",
                round_number=1,
                depth=0
            )
        )
        
        thought_processor._processing_queue.enqueue(
            thought=thought,
            channel_id="test_channel",
            priority=5
        )
        
        # Process
        await thought_processor.process_next_thought()
        
        # Thought should still be marked as completed (action was selected)
        thought_processor._persistence.update_thought_status.assert_called_with(
            thought_id="test_thought",
            status=ThoughtStatus.COMPLETED,
            db_path=thought_processor._db_path
        )
    
    def test_get_queue_stats(self, thought_processor):
        """Test getting queue statistics."""
        # Add some thoughts
        for i in range(5):
            thought = Thought(
                thought_id=f"thought_{i}",
                content=f"Thought {i}",
                source_task_id="test_task",
                status=ThoughtStatus.PENDING,
                created_at=thought_processor.time_service.now_iso(),
                updated_at=thought_processor.time_service.now_iso(),
                thought_depth=0
            )
            
            thought_processor._processing_queue.enqueue(
                thought=thought,
                channel_id="test_channel",
                priority=i
            )
        
        stats = thought_processor.get_queue_stats()
        
        assert stats["total_pending"] == 5
        assert stats["by_priority"][0] == 1  # Priority 0
        assert stats["by_channel"]["test_channel"] == 5
    
    @pytest.mark.asyncio
    async def test_priority_processing_order(self, thought_processor):
        """Test that higher priority thoughts are processed first."""
        # Add thoughts with different priorities
        low_priority = Thought(
            thought_id="low_priority",
            content="Low priority",
            source_task_id="test_task",
            status=ThoughtStatus.PENDING,
            created_at=thought_processor.time_service.now_iso(),
            updated_at=thought_processor.time_service.now_iso(),
            thought_depth=0,
            context=ThoughtContext(
                task_id="test_task",
                correlation_id="low",
                round_number=1,
                depth=0
            )
        )
        
        high_priority = Thought(
            thought_id="high_priority",
            content="High priority",
            source_task_id="test_task",
            status=ThoughtStatus.PENDING,
            created_at=thought_processor.time_service.now_iso(),
            updated_at=thought_processor.time_service.now_iso(),
            thought_depth=0,
            context=ThoughtContext(
                task_id="test_task",
                correlation_id="high",
                round_number=1,
                depth=0
            )
        )
        
        # Add low priority first
        thought_processor._processing_queue.enqueue(
            thought=low_priority,
            channel_id="test_channel",
            priority=1
        )
        
        # Add high priority second
        thought_processor._processing_queue.enqueue(
            thought=high_priority,
            channel_id="test_channel",
            priority=10
        )
        
        # Process next should get high priority
        processed_item = thought_processor._processing_queue.dequeue()
        assert processed_item.thought.thought_id == "high_priority"