"""Unit tests for ThoughtProcessor."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from ciris_engine.logic.processors.core.thought_processor import ThoughtProcessor
from ciris_engine.logic.processors.support.processing_queue import ProcessingQueue, ProcessingQueueItem, ThoughtContent
from ciris_engine.schemas.runtime.models import Task, Thought, ThoughtContext
from ciris_engine.schemas.runtime.enums import (
    TaskStatus, ThoughtStatus, ThoughtType, HandlerActionType
)
from ciris_engine.schemas.dma.decisions import ActionSelectionDecision
from ciris_engine.schemas.dma.results import ActionSelectionDMAResult
from ciris_engine.schemas.actions.parameters import SpeakParams, PonderParams, DeferParams
from ciris_engine.logic.config import ConfigAccessor
from ciris_engine.logic.infrastructure.handlers.base_handler import ActionHandlerDependencies
from ciris_engine.logic.dma.exceptions import DMAFailure
from ciris_engine.logic.registries.circuit_breaker import CircuitBreakerError


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
        from ciris_engine.schemas.actions.parameters import SpeakParams
        mock_llm_bus = Mock()
        mock_llm_bus.select_action = AsyncMock(return_value=ActionSelectionDMAResult(
            selected_action=HandlerActionType.SPEAK,
            action_parameters=SpeakParams(content="Test response"),
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
        with patch('ciris_engine.logic.persistence') as mock_persist:
            # Create a mock thought object
            mock_thought = Mock(
                thought_id="test_thought",
                content="Test thought content",
                source_task_id="test_task",
                status=ThoughtStatus.PENDING,
                thought_type=ThoughtType.STANDARD
            )
            
            # Mock async methods with AsyncMock
            mock_persist.async_get_thought_by_id = AsyncMock(return_value=mock_thought)
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
        # Create mock dependencies
        mock_dma_orchestrator = Mock()
        mock_dma_orchestrator.orchestrate = AsyncMock()
        
        # Mock DMA results that won't trigger critical failure
        mock_dma_results = {
            'csdma': Mock(has_failure=False),
            'pdma': Mock(has_failure=False),
            'asdma': Mock(has_failure=False)
        }
        mock_dma_orchestrator.run_initial_dmas = AsyncMock(return_value=mock_dma_results)
        
        # Mock action selection to return expected result
        mock_action_result = ActionSelectionDMAResult(
            selected_action=HandlerActionType.SPEAK,
            action_parameters=SpeakParams(content="Test response"),
            rationale="Test rationale"
        )
        mock_dma_orchestrator.run_action_selection = AsyncMock(return_value=mock_action_result)
        
        mock_context_builder = Mock()
        mock_context_builder.build_thought_context = AsyncMock(return_value=Mock())
        
        mock_conscience_registry = Mock()
        mock_conscience_registry.apply_consciences = AsyncMock(
            return_value=(mock_action_result, [])  # Return result and empty overrides
        )
        mock_conscience_registry.get_consciences = Mock(return_value=[])  # Empty list of consciences
        
        mock_config = Mock(spec=ConfigAccessor)
        mock_dependencies = Mock(spec=ActionHandlerDependencies)
        
        processor = ThoughtProcessor(
            dma_orchestrator=mock_dma_orchestrator,
            context_builder=mock_context_builder,
            conscience_registry=mock_conscience_registry,
            app_config=mock_config,
            dependencies=mock_dependencies,
            time_service=mock_time_service,
            telemetry_service=None,
            auth_service=None
        )
        return processor
    
    @pytest.mark.asyncio
    async def test_process_thought(self, thought_processor):
        """Test processing a thought."""
        # Create a queue item
        thought = Thought(
            thought_id="test_thought",
            content="Test thought content",
            source_task_id="test_task",
            status=ThoughtStatus.PENDING,
            created_at=thought_processor._time_service.now().isoformat(),
            updated_at=thought_processor._time_service.now().isoformat(),
            thought_type=ThoughtType.STANDARD
        )
        
        item = ProcessingQueueItem.from_thought(thought)
        
        # Process - the mocks are already set up in the fixture
        result = await thought_processor.process_thought(item)
        
        assert result is not None
        # The conscience system may change the action, so check that we got a valid result
        assert result.selected_action in [HandlerActionType.SPEAK, HandlerActionType.PONDER]
    
    @pytest.mark.asyncio
    async def test_process_thought_with_ponder(self, thought_processor):
        """Test processing a thought that results in pondering."""
        # Create a queue item
        thought = Thought(
            thought_id="test_thought_ponder",
            content="This is a complex question",
            source_task_id="test_task",
            status=ThoughtStatus.PENDING,
            created_at=thought_processor._time_service.now().isoformat(),
            updated_at=thought_processor._time_service.now().isoformat(),
            thought_type=ThoughtType.STANDARD
        )
        
        item = ProcessingQueueItem.from_thought(thought)
        
        # Mock DMA result for PONDER
        mock_result = ActionSelectionDMAResult(
            selected_action=HandlerActionType.PONDER,
            action_parameters=PonderParams(questions=["What does this mean?"]),
            rationale="Need to think about this"
        )
        thought_processor.dma_orchestrator.run_action_selection = AsyncMock(return_value=mock_result)
        
        # Process
        result = await thought_processor.process_thought(item)
        
        assert result is not None
        assert result.selected_action == HandlerActionType.PONDER
    
    @pytest.mark.asyncio
    async def test_process_thought_with_defer(self, thought_processor):
        """Test processing a thought that results in deferral."""
        # Create a queue item
        thought = Thought(
            thought_id="test_thought_defer",
            content="I need to wait for something",
            source_task_id="test_task",
            status=ThoughtStatus.PENDING,
            created_at=thought_processor._time_service.now().isoformat(),
            updated_at=thought_processor._time_service.now().isoformat(),
            thought_type=ThoughtType.STANDARD
        )
        
        item = ProcessingQueueItem.from_thought(thought)
        
        # Mock DMA result for DEFER
        mock_result = ActionSelectionDMAResult(
            selected_action=HandlerActionType.DEFER,
            action_parameters=DeferParams(reason="Waiting for user input"),
            rationale="Need to wait"
        )
        thought_processor.dma_orchestrator.run_action_selection = AsyncMock(return_value=mock_result)
        
        # Process
        result = await thought_processor.process_thought(item)
        
        assert result is not None
        assert result.selected_action == HandlerActionType.DEFER
    
    @pytest.mark.asyncio
    async def test_process_thought_with_error(self, thought_processor):
        """Test processing a thought that encounters an error."""
        # Create a queue item
        thought = Thought(
            thought_id="test_thought_error",
            content="This will fail",
            source_task_id="test_task",
            status=ThoughtStatus.PENDING,
            created_at=thought_processor._time_service.now().isoformat(),
            updated_at=thought_processor._time_service.now().isoformat(),
            thought_type=ThoughtType.STANDARD
        )
        
        item = ProcessingQueueItem.from_thought(thought)
        
        # Mock DMA to raise error
        thought_processor.dma_orchestrator.run_initial_dmas = AsyncMock(side_effect=DMAFailure("Test error"))
        
        # Process should handle error gracefully
        result = await thought_processor.process_thought(item)
        
        # Should return DEFER result on DMA error
        assert result is not None
        assert result.selected_action == HandlerActionType.DEFER
        # action_parameters is a dict when model_dump() is called
        if isinstance(result.action_parameters, dict):
            assert "DMA timeout" in result.action_parameters["reason"]
        else:
            assert "DMA timeout" in result.action_parameters.reason
    
    @pytest.mark.asyncio
    async def test_process_thought_with_circuit_breaker(self, thought_processor):
        """Test processing thought with circuit breaker error."""
        # Create a queue item
        thought = Thought(
            thought_id="test_thought_cb",
            content="Circuit breaker test",
            source_task_id="test_task",
            status=ThoughtStatus.PENDING,
            created_at=thought_processor._time_service.now().isoformat(),
            updated_at=thought_processor._time_service.now().isoformat(),
            thought_type=ThoughtType.STANDARD
        )
        
        item = ProcessingQueueItem.from_thought(thought)
        
        # Mock DMA to raise circuit breaker error
        thought_processor.dma_orchestrator.run_initial_dmas = AsyncMock(
            side_effect=CircuitBreakerError("Circuit breaker open")
        )
        
        # Process should handle circuit breaker gracefully - it doesn't catch CB errors
        with pytest.raises(CircuitBreakerError):
            await thought_processor.process_thought(item)
    
    @pytest.mark.asyncio
    async def test_process_thought_with_conscience(self, thought_processor):
        """Test processing thought with conscience evaluation."""
        # Create a queue item  
        thought = Thought(
            thought_id="test_thought_conscience",
            content="Should I do something questionable?",
            source_task_id="test_task",
            status=ThoughtStatus.PENDING,
            created_at=thought_processor._time_service.now().isoformat(),
            updated_at=thought_processor._time_service.now().isoformat(),
            thought_type=ThoughtType.STANDARD
        )
        
        item = ProcessingQueueItem.from_thought(thought)
        
        # Mock DMA result
        mock_result = ActionSelectionDMAResult(
            selected_action=HandlerActionType.SPEAK,
            action_parameters=SpeakParams(content="I'll think carefully about this"),
            rationale="Being thoughtful"
        )
        thought_processor.dma_orchestrator.orchestrate = AsyncMock(return_value=mock_result)
        
        # Mock conscience evaluation
        mock_conscience_result = Mock(approved=True, feedback="Good approach")
        thought_processor.conscience_registry.evaluate = AsyncMock(return_value=mock_conscience_result)
        
        # Process
        result = await thought_processor.process_thought(item)
        
        assert result is not None
    
    @pytest.mark.asyncio 
    async def test_process_thought_task_complete(self, thought_processor):
        """Test processing thought that completes a task."""
        # Create a queue item
        thought = Thought(
            thought_id="test_thought_complete",
            content="Task is done",
            source_task_id="test_task",
            status=ThoughtStatus.PENDING,
            created_at=thought_processor._time_service.now().isoformat(),
            updated_at=thought_processor._time_service.now().isoformat(),
            thought_type=ThoughtType.STANDARD
        )
        
        item = ProcessingQueueItem.from_thought(thought)
        
        # Mock DMA result for TASK_COMPLETE
        from ciris_engine.schemas.actions.parameters import TaskCompleteParams
        task_complete_params = TaskCompleteParams(
            completion_reason="Successfully completed"
        )
        mock_result = ActionSelectionDMAResult(
            selected_action=HandlerActionType.TASK_COMPLETE,
            action_parameters=task_complete_params,
            rationale="Task finished"
        )
        thought_processor.dma_orchestrator.run_action_selection = AsyncMock(return_value=mock_result)
        
        # Process
        result = await thought_processor.process_thought(item)
        
        assert result is not None
        assert result.selected_action == HandlerActionType.TASK_COMPLETE
    
    @pytest.mark.asyncio
    async def test_process_thought_with_context(self, thought_processor):
        """Test processing thought with additional context."""
        # Create a queue item with context
        thought = Thought(
            thought_id="test_thought_context",
            content="Contextual thought",
            source_task_id="test_task",
            status=ThoughtStatus.PENDING,
            created_at=thought_processor._time_service.now().isoformat(),
            updated_at=thought_processor._time_service.now().isoformat(),
            thought_type=ThoughtType.STANDARD
        )
        
        item = ProcessingQueueItem.from_thought(
            thought,
            initial_ctx={"user_id": "test_user", "session_id": "test_session"}
        )
        
        # Mock context builder - it's actually build_thought_context that's called
        thought_processor.context_builder.build_thought_context = AsyncMock(
            return_value={"full_context": True}
        )
        
        # Mock DMA result
        mock_result = ActionSelectionDMAResult(
            selected_action=HandlerActionType.SPEAK,
            action_parameters=SpeakParams(content="Context aware response"),
            rationale="Using context"
        )
        thought_processor.dma_orchestrator.orchestrate = AsyncMock(return_value=mock_result)
        
        # Process
        result = await thought_processor.process_thought(item, context={"additional": "context"})
        
        assert result is not None
        # Verify context builder was called
        thought_processor.context_builder.build_thought_context.assert_called_once()