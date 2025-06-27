"""Unit tests for AgentProcessor."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from ciris_engine.logic.processors.core.main_processor import AgentProcessor
from ciris_engine.schemas.processors.states import AgentState
from ciris_engine.schemas.processors.results import (
    WakeupResult, WorkResult, PlayResult, SolitudeResult, DreamResult, ShutdownResult
)
from ciris_engine.schemas.processors.main import ProcessorMetrics
from ciris_engine.logic.config import ConfigAccessor


class TestAgentProcessor:
    """Test cases for AgentProcessor."""
    
    @pytest.fixture
    def mock_time_service(self):
        """Create mock time service."""
        current_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        return Mock(
            now=Mock(return_value=current_time),
            now_iso=Mock(return_value=current_time.isoformat())
        )
    
    @pytest.fixture
    def mock_config(self):
        """Create mock config accessor."""
        config = Mock(spec=ConfigAccessor)
        config.get = Mock(side_effect=lambda key, default=None: {
            'agent.startup_state': 'WAKEUP',
            'agent.max_rounds': 100,
            'agent.round_timeout': 300,
            'agent.state_transition_delay': 1.0
        }.get(key, default))
        return config
    
    @pytest.fixture
    def mock_services(self, mock_time_service):
        """Create mock services."""
        return {
            'time_service': mock_time_service,
            'telemetry_service': Mock(memorize_metric=AsyncMock()),
            'memory_service': Mock(memorize=AsyncMock()),
            'identity_manager': Mock(
                get_identity=Mock(return_value={'name': 'TestAgent'})
            )
        }
    
    @pytest.fixture
    def mock_processors(self):
        """Create mock state processors."""
        processors = {}
        
        # Map states to their specific result types
        result_types = {
            'wakeup': WakeupResult(thoughts_processed=1, wakeup_complete=True, errors=0, duration_seconds=1.0),
            'work': WorkResult(tasks_processed=1, thoughts_processed=1, errors=0, duration_seconds=1.0),
            'play': PlayResult(thoughts_processed=1, errors=0, duration_seconds=1.0),
            'solitude': SolitudeResult(thoughts_processed=1, errors=0, duration_seconds=1.0),
            'dream': DreamResult(thoughts_processed=1, errors=0, duration_seconds=1.0),
            'shutdown': ShutdownResult(tasks_cleaned=1, shutdown_ready=True, errors=0, duration_seconds=1.0)
        }
        
        for state in ['wakeup', 'work', 'play', 'solitude', 'dream', 'shutdown']:
            processor = Mock()
            processor.get_supported_states = Mock(return_value=[getattr(AgentState, state.upper())])
            processor.can_process = AsyncMock(return_value=True)
            processor.initialize = AsyncMock(return_value=True)
            processor.process = AsyncMock(return_value=result_types[state])
            processor.cleanup = AsyncMock(return_value=True)
            processor.get_metrics = Mock(return_value=ProcessorMetrics(processor_name=f"{state.capitalize()}Processor"))
            processors[state] = processor
        return processors
    
    @pytest.fixture
    def main_processor(self, mock_config, mock_services, mock_processors, mock_time_service):
        """Create AgentProcessor instance."""
        # Mock required dependencies
        mock_identity = Mock(
            agent_id="test_agent",
            name="TestAgent",
            purpose="Testing"
        )
        mock_thought_processor = Mock()
        mock_action_dispatcher = Mock()
        
        processor = AgentProcessor(
            app_config=mock_config,
            agent_identity=mock_identity,
            thought_processor=mock_thought_processor,
            action_dispatcher=mock_action_dispatcher,
            services=mock_services,
            startup_channel_id="test_channel",
            time_service=mock_time_service,
            runtime=None
        )
        
        # Replace the state processors with our mocks
        processor.wakeup_processor = mock_processors['wakeup']
        processor.work_processor = mock_processors['work']
        processor.play_processor = mock_processors['play']
        processor.solitude_processor = mock_processors['solitude']
        processor.dream_processor = mock_processors['dream']
        processor.shutdown_processor = mock_processors['shutdown']
        
        return processor
    
    @pytest.mark.asyncio
    async def test_initialize(self, main_processor):
        """Test processor initialization."""
        result = await main_processor.initialize()
        
        assert result is True
        assert main_processor._current_state == AgentState.WAKEUP
        assert main_processor._running is True
    
    @pytest.mark.asyncio
    async def test_start_processing(self, main_processor):
        """Test start processing with limited rounds."""
        await main_processor.initialize()
        
        # Process 3 rounds
        await main_processor.start_processing(num_rounds=3)
        
        # Should have processed 3 rounds
        assert main_processor._round_count == 3
        assert main_processor._running is False
    
    @pytest.mark.asyncio
    async def test_process_single_round(self, main_processor, mock_processors):
        """Test processing a single round."""
        await main_processor.initialize()
        
        result = await main_processor._process_round()
        
        assert result is True
        # Should call the wakeup processor
        mock_processors['wakeup'].process.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_state_transition(self, main_processor, mock_processors):
        """Test state transition."""
        await main_processor.initialize()
        
        # Mock processor to request transition
        mock_processors['wakeup'].process.return_value = ProcessingResult(
            success=True,
            items_processed=1,
            should_transition=True,
            next_state=AgentState.WORK
        )
        
        await main_processor._process_round()
        
        # Should transition to WORK
        assert main_processor._current_state == AgentState.WORK
        assert len(main_processor._state_history) > 0
    
    @pytest.mark.asyncio
    async def test_handle_processor_error(self, main_processor, mock_processors):
        """Test handling processor errors."""
        await main_processor.initialize()
        
        # Mock processor to raise error
        mock_processors['wakeup'].process.side_effect = Exception("Test error")
        
        # Should handle error gracefully
        result = await main_processor._process_round()
        
        assert result is True  # Should continue
        assert main_processor._error_count > 0
    
    @pytest.mark.asyncio
    async def test_max_consecutive_errors(self, main_processor, mock_processors):
        """Test max consecutive errors triggers shutdown."""
        await main_processor.initialize()
        main_processor._max_consecutive_errors = 3
        
        # Mock processor to always error
        mock_processors['wakeup'].process.side_effect = Exception("Test error")
        
        # Process multiple rounds
        for _ in range(4):
            await main_processor._process_round()
        
        # Should transition to SHUTDOWN after max errors
        assert main_processor._current_state == AgentState.SHUTDOWN
    
    @pytest.mark.asyncio
    async def test_round_timeout(self, main_processor, mock_processors):
        """Test round timeout handling."""
        await main_processor.initialize()
        main_processor._round_timeout = 0.1  # 100ms timeout
        
        # Mock processor to take too long
        async def slow_process(round_num):
            await asyncio.sleep(0.5)
            return ProcessingResult(success=True)
        
        mock_processors['wakeup'].process = slow_process
        
        # Should timeout
        result = await main_processor._process_round()
        
        assert result is True
        assert main_processor._timeout_count > 0
    
    @pytest.mark.asyncio
    async def test_stop_processing(self, main_processor):
        """Test stopping processing."""
        await main_processor.initialize()
        
        # Start processing in background
        task = asyncio.create_task(main_processor.start_processing())
        
        # Let it process a bit
        await asyncio.sleep(0.1)
        
        # Stop processing
        await main_processor.stop_processing()
        
        # Wait for task to complete
        await task
        
        assert main_processor._running is False
        assert main_processor._stop_requested is True
    
    @pytest.mark.asyncio
    async def test_emergency_stop(self, main_processor):
        """Test emergency stop."""
        await main_processor.initialize()
        
        await main_processor.emergency_stop("Test emergency")
        
        assert main_processor._running is False
        assert main_processor._current_state == AgentState.SHUTDOWN
        assert "emergency" in str(main_processor._shutdown_reason).lower()
    
    def test_get_current_state(self, main_processor):
        """Test getting current state."""
        main_processor._current_state = AgentState.WORK
        
        assert main_processor.get_current_state() == AgentState.WORK
    
    def test_get_state_history(self, main_processor):
        """Test getting state history."""
        # Add some history
        main_processor._state_history.append(
            StateTransition(
                from_state=AgentState.WAKEUP,
                to_state=AgentState.WORK,
                timestamp=main_processor.time_service.now(),
                reason="Normal transition"
            )
        )
        
        history = main_processor.get_state_history()
        
        assert len(history) == 1
        assert history[0].from_state == AgentState.WAKEUP
        assert history[0].to_state == AgentState.WORK
    
    def test_get_processor_metrics(self, main_processor):
        """Test getting processor metrics."""
        main_processor._round_count = 10
        main_processor._successful_rounds = 8
        main_processor._error_count = 2
        
        metrics = main_processor.get_processor_metrics()
        
        assert metrics['total_rounds'] == 10
        assert metrics['successful_rounds'] == 8
        assert metrics['error_count'] == 2
        assert metrics['current_state'] == 'WAKEUP'
    
    @pytest.mark.asyncio
    async def test_validate_transition(self, main_processor):
        """Test state transition validation."""
        # Valid transitions
        assert await main_processor._validate_transition(AgentState.WAKEUP, AgentState.WORK) is True
        assert await main_processor._validate_transition(AgentState.WORK, AgentState.PLAY) is True
        
        # Invalid transition (can't go from SHUTDOWN to WORK)
        assert await main_processor._validate_transition(AgentState.SHUTDOWN, AgentState.WORK) is False
    
    @pytest.mark.asyncio
    async def test_transition_to_same_state(self, main_processor):
        """Test transitioning to same state is allowed."""
        await main_processor.initialize()
        
        # Should allow same state transition
        success = await main_processor._transition_to_state(AgentState.WAKEUP)
        
        assert success is True
        assert main_processor._current_state == AgentState.WAKEUP
    
    @pytest.mark.asyncio
    async def test_processor_not_found(self, main_processor):
        """Test handling missing processor for state."""
        await main_processor.initialize()
        
        # Remove work processor
        del main_processor._state_processors['work']
        
        # Try to transition to WORK
        success = await main_processor._transition_to_state(AgentState.WORK)
        
        assert success is False
        assert main_processor._current_state == AgentState.WAKEUP  # Should stay in current state
    
    @pytest.mark.asyncio
    async def test_state_transition_delay(self, main_processor):
        """Test state transition delay."""
        await main_processor.initialize()
        main_processor._state_transition_delay = 0.1
        
        start_time = asyncio.get_event_loop().time()
        await main_processor._transition_to_state(AgentState.WORK)
        end_time = asyncio.get_event_loop().time()
        
        # Should have delayed
        assert (end_time - start_time) >= 0.1
    
    @pytest.mark.asyncio
    async def test_cleanup(self, main_processor, mock_processors):
        """Test cleanup."""
        await main_processor.initialize()
        
        # Process some rounds
        await main_processor.start_processing(num_rounds=2)
        
        # Cleanup
        result = await main_processor.cleanup()
        
        assert result is True
        # Should cleanup current processor
        mock_processors['wakeup'].cleanup.assert_called()
    
    @pytest.mark.asyncio
    async def test_max_rounds_limit(self, main_processor):
        """Test max rounds limit."""
        await main_processor.initialize()
        main_processor._max_rounds = 5
        
        # Try to process more than max
        await main_processor.start_processing(num_rounds=10)
        
        # Should stop at max rounds
        assert main_processor._round_count == 5
    
    
    @pytest.mark.asyncio
    async def test_record_state_transition(self, main_processor):
        """Test recording state transitions."""
        await main_processor.initialize()
        
        # Record a transition
        await main_processor._record_state_transition(
            AgentState.WAKEUP,
            AgentState.WORK,
            "Test transition"
        )
        
        # Check history
        assert len(main_processor._state_history) == 1
        assert main_processor._state_history[0].reason == "Test transition"
        
        # Check telemetry was recorded
        main_processor.telemetry_service.memorize_metric.assert_called()
    
    @pytest.mark.asyncio
    async def test_processor_initialization_failure(self, main_processor, mock_processors):
        """Test handling processor initialization failure."""
        await main_processor.initialize()
        
        # Mock processor init to fail
        mock_processors['work'].initialize.return_value = False
        
        # Try to transition to WORK
        success = await main_processor._transition_to_state(AgentState.WORK)
        
        assert success is False
        assert main_processor._current_state == AgentState.WAKEUP