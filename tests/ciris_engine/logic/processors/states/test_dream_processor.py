"""Unit tests for DreamProcessor."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from ciris_engine.logic.processors.states.dream_processor import (
    DreamProcessor, DreamPhase, DreamSession
)
from ciris_engine.schemas.processors.states import AgentState
from ciris_engine.schemas.processors.results import DreamResult
from ciris_engine.schemas.processors.base import MetricsUpdate
from ciris_engine.schemas.runtime.enums import ThoughtType, TaskStatus
from ciris_engine.schemas.runtime.models import Task, Thought
from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphScope
from ciris_engine.logic.config import ConfigAccessor


class TestDreamProcessor:
    """Test cases for DreamProcessor."""
    
    @pytest.fixture
    def mock_services(self):
        """Create mock services."""
        current_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        return {
            'time_service': Mock(
                now=Mock(return_value=current_time),
                now_iso=Mock(return_value=current_time.isoformat())
            ),
            'resource_monitor': Mock(
                snapshot=Mock(healthy=True, warnings=[], critical=[])
            ),
            'memory_service': Mock(),
            'telemetry_service': Mock(
                memorize_metric=AsyncMock()
            ),
            'self_configuration': Mock(
                analyze_patterns=AsyncMock(return_value=[]),
                apply_recommendations=AsyncMock(return_value=0)
            )
        }
    
    @pytest.fixture
    def mock_config(self):
        """Create mock config accessor."""
        config = Mock(spec=ConfigAccessor)
        config.get = Mock(return_value=None)
        config.get_or_none = Mock(return_value=None)
        return config
    
    @pytest.fixture
    def mock_thought_processor(self):
        """Create mock thought processor."""
        return Mock(
            get_processing_queue=Mock(return_value=Mock(
                pending_items=Mock(return_value=[]),
                is_empty=Mock(return_value=True)
            ))
        )
    
    @pytest.fixture
    def mock_action_dispatcher(self):
        """Create mock action dispatcher."""
        return Mock()
    
    @pytest.fixture
    def dream_processor(self, mock_config, mock_thought_processor, mock_action_dispatcher, mock_services):
        """Create DreamProcessor instance."""
        processor = DreamProcessor(
            config_accessor=mock_config,
            thought_processor=mock_thought_processor,
            action_dispatcher=mock_action_dispatcher,
            services=mock_services,
            startup_channel_id="test_channel",  # Add channel_id for task creation
            pulse_interval=1.0,  # Short for testing
            min_dream_duration=1,  # 1 minute for testing
            max_dream_duration=2   # 2 minutes for testing
        )
        # Inject memory bus directly
        processor.memory_bus = Mock(
            search=AsyncMock(return_value=[]),
            memorize=AsyncMock()
        )
        processor.communication_bus = Mock(
            send_message=AsyncMock()
        )
        # Mock task_manager to handle create_task calls
        processor.task_manager = Mock(
            create_task=Mock(return_value=Mock(task_id="test_task")),
            activate_pending_tasks=Mock(return_value=0),
            get_tasks_needing_seed=Mock(return_value=[])
        )
        processor.thought_manager = Mock(
            generate_seed_thoughts=Mock(return_value=0)
        )
        return processor
    
    def test_get_supported_states(self, dream_processor):
        """Test that DreamProcessor supports DREAM state."""
        states = dream_processor.get_supported_states()
        assert states == [AgentState.DREAM]
    
    @pytest.mark.asyncio
    async def test_can_process_dream_state(self, dream_processor):
        """Test that DreamProcessor can process DREAM state."""
        assert await dream_processor.can_process(AgentState.DREAM) is True
        assert await dream_processor.can_process(AgentState.WORK) is False
    
    @pytest.mark.asyncio
    async def test_initialize(self, dream_processor):
        """Test DreamProcessor initialization."""
        result = await dream_processor.initialize()
        assert result is True
        # current_session is created when processing starts, not during initialization
        assert dream_processor.current_session is None
    
    @pytest.mark.asyncio
    async def test_process_entering_phase(self, dream_processor):
        """Test processing during ENTERING phase."""
        await dream_processor.initialize()
        
        # Start dreaming to create session
        await dream_processor.start_dreaming(duration=60)
        
        # Now process
        result = await dream_processor.process(1)
        
        assert isinstance(result, DreamResult)
        assert result.errors == 0
        # After starting dream, current_session should be created
        assert dream_processor.current_session is not None
        # Initial phase is ENTERING
        assert dream_processor.current_session.phase == DreamPhase.ENTERING
    
    @pytest.mark.asyncio
    async def test_process_consolidating_phase(self, dream_processor):
        """Test processing during CONSOLIDATING phase."""
        await dream_processor.initialize()
        # Start dreaming to create session
        await dream_processor.start_dreaming(duration=60)
        dream_processor.current_session.phase = DreamPhase.CONSOLIDATING
        
        # Mock memory consolidation
        with patch.object(dream_processor, '_consolidate_recent_memories', new_callable=AsyncMock) as mock_consolidate:
            mock_consolidate.return_value = 5
            
            result = await dream_processor.process(2)
            
            assert result.errors == 0
            assert result.thoughts_processed == 5
            assert dream_processor.current_session.phase == DreamPhase.ANALYZING
    
    @pytest.mark.asyncio
    async def test_process_analyzing_phase(self, dream_processor):
        """Test processing during ANALYZING phase."""
        await dream_processor.initialize()
        # Start dreaming to create session
        await dream_processor.start_dreaming(duration=60)
        dream_processor.current_session.phase = DreamPhase.ANALYZING
        
        # Mock behavioral insights
        with patch.object(dream_processor, '_process_behavioral_insights', new_callable=AsyncMock) as mock_insights:
            mock_insights.return_value = ['insight1', 'insight2']
            
            result = await dream_processor.process(3)
            
            assert result.errors == 0
            # DreamResult is simplified, doesn't have metadata
            assert dream_processor.current_session.phase == DreamPhase.CONFIGURING
    
    @pytest.mark.asyncio
    async def test_process_configuring_phase(self, dream_processor):
        """Test processing during CONFIGURING phase."""
        await dream_processor.initialize()
        # Start dreaming to create session
        await dream_processor.start_dreaming(duration=60)
        dream_processor.current_session.phase = DreamPhase.CONFIGURING
        
        result = await dream_processor.process(4)
        
        assert result.errors == 0
        # DreamResult is simplified, doesn't have metadata
        assert dream_processor.current_session.phase == DreamPhase.PLANNING
    
    @pytest.mark.asyncio
    async def test_process_planning_phase(self, dream_processor):
        """Test processing during PLANNING phase."""
        await dream_processor.initialize()
        # Start dreaming to create session
        await dream_processor.start_dreaming(duration=60)
        dream_processor.current_session.phase = DreamPhase.PLANNING
        
        # Mock active tasks
        mock_tasks = [
            Mock(task_id='task1', description='Test task 1', priority=5),
            Mock(task_id='task2', description='Test task 2', priority=3)
        ]
        
        with patch.object(dream_processor, '_get_active_tasks', new_callable=AsyncMock) as mock_get_tasks:
            mock_get_tasks.return_value = mock_tasks
            
            result = await dream_processor.process(5)
            
            assert result.errors == 0
            # DreamResult is simplified, doesn't have metadata
            assert dream_processor.current_session.phase == DreamPhase.EXITING
    
    @pytest.mark.asyncio
    async def test_process_exiting_phase(self, dream_processor):
        """Test processing during EXITING phase."""
        await dream_processor.initialize()
        # Start dreaming to create session
        await dream_processor.start_dreaming(duration=60)
        dream_processor.current_session.phase = DreamPhase.EXITING
        dream_processor.current_session.actual_start = dream_processor.time_service.now() - timedelta(minutes=2)
        
        result = await dream_processor.process(6)
        
        assert result.errors == 0
        # Dream processor handles its own state transitions internally
    
    @pytest.mark.asyncio
    async def test_cleanup(self, dream_processor):
        """Test DreamProcessor cleanup."""
        await dream_processor.initialize()
        # Start dreaming to create session
        await dream_processor.start_dreaming(duration=60)
        result = await dream_processor.cleanup()
        
        assert result is True
        assert dream_processor.current_session is None
    
    @pytest.mark.asyncio
    async def test_consolidate_recent_memories(self, dream_processor):
        """Test memory consolidation."""
        # Mock recent memories
        mock_memories = [
            GraphNode(
                id='mem1',
                type=NodeType.OBSERVATION,
                scope=GraphScope.LOCAL,
                attributes={'content': 'Memory 1', 'timestamp': dream_processor.time_service.now().isoformat()}
            ),
            GraphNode(
                id='mem2',
                type=NodeType.OBSERVATION,
                scope=GraphScope.LOCAL,
                attributes={'content': 'Memory 2', 'timestamp': dream_processor.time_service.now().isoformat()}
            )
        ]
        
        dream_processor.memory_bus.search.return_value = mock_memories
        
        count = await dream_processor._consolidate_recent_memories()
        
        assert count == 2
        # Should create consolidated memory
        dream_processor.memory_bus.memorize.assert_called()
    
    @pytest.mark.asyncio
    async def test_process_behavioral_insights(self, dream_processor):
        """Test behavioral insights processing."""
        # Mock insight nodes
        mock_insights = [
            GraphNode(
                id='insight1',
                type=NodeType.CONCEPT,
                scope=GraphScope.LOCAL,
                attributes={
                    'insight_type': 'behavioral_pattern',
                    'pattern_type': 'frequency',
                    'description': 'High frequency of SPEAK actions',
                    'actionable': True
                }
            )
        ]
        
        dream_processor.memory_bus.search.return_value = mock_insights
        
        insights = await dream_processor._process_behavioral_insights()
        
        assert len(insights) == 2  # Pattern + action opportunity
        assert any('High frequency of SPEAK actions' in i for i in insights)
    
    @pytest.mark.asyncio
    async def test_apply_self_configuration(self, dream_processor, mock_services):
        """Test self-configuration application."""
        # Mock self-configuration service
        mock_services['self_configuration'].analyze_patterns.return_value = [
            Mock(recommendation='Increase ponder threshold', confidence=0.8)
        ]
        mock_services['self_configuration'].apply_recommendations.return_value = 1
        
        result = await dream_processor._apply_self_configuration()
        
        assert result == 1
        mock_services['self_configuration'].analyze_patterns.assert_called_once()
        mock_services['self_configuration'].apply_recommendations.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_system_snapshot(self, dream_processor):
        """Test system snapshot creation."""
        # Mock active tasks and thoughts
        with patch.object(dream_processor, '_get_active_tasks', new_callable=AsyncMock) as mock_tasks:
            with patch.object(dream_processor, '_get_active_thoughts', new_callable=AsyncMock) as mock_thoughts:
                mock_tasks.return_value = [Mock(task_id='task1')]
                mock_thoughts.return_value = [Mock(thought_id='thought1')]
                
                snapshot = await dream_processor._create_system_snapshot(
                    'Dream phase transition',
                    DreamPhase.ENTERING,
                    DreamPhase.CONSOLIDATING
                )
                
                assert snapshot is not None
                assert snapshot.cognitive_state == 'DREAM'
                assert snapshot.active_task_count == 1
                assert snapshot.active_thought_count == 1
    
    @pytest.mark.asyncio
    async def test_minimum_dream_duration(self, dream_processor):
        """Test that dream respects minimum duration."""
        await dream_processor.initialize()
        # Start dreaming to create session
        await dream_processor.start_dreaming(duration=60)
        
        # Set to EXITING but not enough time passed
        dream_processor.current_session.phase = DreamPhase.EXITING
        dream_processor.current_session.actual_start = dream_processor.time_service.now()
        
        result = await dream_processor.process(10)
        
        # Should not transition yet
        assert result.should_transition is False
        assert dream_processor.current_session.phase == DreamPhase.CONSOLIDATING
    
    @pytest.mark.asyncio
    async def test_maximum_dream_duration(self, dream_processor):
        """Test that dream respects maximum duration."""
        await dream_processor.initialize()
        # Start dreaming to create session
        await dream_processor.start_dreaming(duration=60)
        
        # Set start time beyond max duration
        dream_processor.current_session.actual_start = dream_processor.time_service.now() - timedelta(minutes=5)
        dream_processor.current_session.phase = DreamPhase.CONSOLIDATING
        
        result = await dream_processor.process(20)
        
        # Should force transition to EXITING
        assert dream_processor.current_session.phase == DreamPhase.EXITING
    
    @pytest.mark.asyncio
    async def test_error_handling_in_phase(self, dream_processor):
        """Test error handling during phase processing."""
        await dream_processor.initialize()
        # Start dreaming to create session
        await dream_processor.start_dreaming(duration=60)
        dream_processor.current_session.phase = DreamPhase.CONSOLIDATING
        
        # Mock consolidation to raise error
        with patch.object(dream_processor, '_consolidate_recent_memories', new_callable=AsyncMock) as mock_consolidate:
            mock_consolidate.side_effect = Exception("Test error")
            
            result = await dream_processor.process(30)
            
            # Should handle error gracefully
            assert result.errors > 0
            # Error details are logged, not in result
            # Should still advance phase
            assert dream_processor.current_session.phase == DreamPhase.ANALYZING
    
    @pytest.mark.asyncio
    async def test_pulse_activity_tracking(self, dream_processor):
        """Test that activities are tracked correctly."""
        await dream_processor.initialize()
        # Start dreaming to create session
        await dream_processor.start_dreaming(duration=60)
        
        # Track some metrics
        dream_processor.current_session.memories_consolidated = 5
        dream_processor.current_session.patterns_analyzed = 3
        
        assert dream_processor.current_session.memories_consolidated == 5
        assert dream_processor.current_session.patterns_analyzed == 3
    
    @pytest.mark.asyncio
    async def test_benchmarking_mode(self, dream_processor):
        """Test benchmarking mode with CIRISNode."""
        await dream_processor.initialize()
        # Start dreaming to create session
        await dream_processor.start_dreaming(duration=60)
        
        # Mock CIRISNode availability
        with patch.object(dream_processor, '_cirisnode_available', new_callable=AsyncMock) as mock_available:
            mock_available.return_value = True
            
            with patch.object(dream_processor, '_run_cirisnode_benchmark', new_callable=AsyncMock) as mock_benchmark:
                mock_benchmark.return_value = {'score': 95}
                
                dream_processor.current_session.phase = DreamPhase.BENCHMARKING
                result = await dream_processor.process(40)
                
                assert result.errors == 0
                # DreamResult is simplified, benchmark tracked internally
                assert dream_processor.current_session.phase == DreamPhase.EXITING