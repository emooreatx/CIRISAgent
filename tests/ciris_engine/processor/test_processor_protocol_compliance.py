"""
Comprehensive unit tests for processor protocol compliance and state handling.
Tests all processor types: Wakeup, Work, Play, Solitude, Dream, and Main.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from ciris_engine.processor.main_processor import AgentProcessor
from ciris_engine.processor.wakeup_processor import WakeupProcessor
from ciris_engine.processor.work_processor import WorkProcessor
from ciris_engine.processor.play_processor import PlayProcessor
from ciris_engine.processor.solitude_processor import SolitudeProcessor
from ciris_engine.processor.dream_processor import DreamProcessor
from ciris_engine.protocols.processor_interface import ProcessorInterface
from ciris_engine.schemas.states_v1 import AgentState
from ciris_engine.schemas.config_schemas_v1 import AppConfig, AgentProfile, WorkflowConfig
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus
from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought


# Mock classes for testing
class MockAppConfig:
    def __init__(self):
        self.workflow = WorkflowConfig(max_active_tasks=10, max_active_thoughts=50)


class MockAgentProfile:
    def __init__(self, name="TestAgent"):
        self.name = name
        self.description = "Test agent for unit testing"


class MockThoughtProcessor:
    pass


class MockActionDispatcher:
    pass


class MockServices(dict):
    def __init__(self):
        super().__init__()
        self["service_registry"] = MagicMock()
        self.services = self


class MockStateManager:
    def __init__(self, initial_state=AgentState.SHUTDOWN):
        self.current_state = initial_state
        self.state_duration = 0.0
        self.metadata = {}
    
    def get_state(self):
        return self.current_state
    
    def transition_to(self, state):
        self.current_state = state
        return True
    
    def get_state_duration(self):
        return self.state_duration
    
    def update_state_metadata(self, key, value):
        self.metadata[key] = value


@pytest.fixture
def mock_config():
    return MockAppConfig()


@pytest.fixture
def mock_profile():
    return MockAgentProfile()


@pytest.fixture
def mock_thought_processor():
    return MockThoughtProcessor()


@pytest.fixture
def mock_action_dispatcher():
    return MockActionDispatcher()


@pytest.fixture
def mock_services():
    return MockServices()


class TestProcessorInterface:
    """Test that all processors implement ProcessorInterface correctly."""
    
    def test_all_processors_implement_interface(self):
        """Verify all processor classes implement ProcessorInterface."""
        processors = [AgentProcessor, WakeupProcessor, WorkProcessor, PlayProcessor, SolitudeProcessor]
        
        for processor_class in processors:
            assert issubclass(processor_class, ProcessorInterface), \
                f"{processor_class.__name__} does not implement ProcessorInterface"
    
    def test_required_methods_exist(self):
        """Verify all processors have required protocol methods."""
        processors = [AgentProcessor, WakeupProcessor, WorkProcessor, PlayProcessor, SolitudeProcessor]
        required_methods = ['start_processing', 'stop_processing', 'get_status', 'process']
        
        for processor_class in processors:
            for method in required_methods:
                assert hasattr(processor_class, method), \
                    f"{processor_class.__name__} missing {method}"


class TestWakeupProcessor:
    """Comprehensive tests for WakeupProcessor."""
    
    @pytest.fixture
    def wakeup_processor(self, mock_config, mock_profile, mock_thought_processor, 
                        mock_action_dispatcher, mock_services):
        with patch('ciris_engine.persistence.task_exists', return_value=False), \
             patch('ciris_engine.persistence.add_task'), \
             patch('ciris_engine.persistence.get_task_by_id'), \
             patch('ciris_engine.persistence.get_thoughts_by_task_id', return_value=[]):
            return WakeupProcessor(
                app_config=mock_config,
                thought_processor=mock_thought_processor,
                action_dispatcher=mock_action_dispatcher,
                services=mock_services,
                startup_channel_id="test_channel",
                agent_profile=mock_profile
            )
    
    def test_wakeup_processor_initialization(self, wakeup_processor):
        """Test WakeupProcessor initializes correctly."""
        assert isinstance(wakeup_processor, WakeupProcessor)
        assert isinstance(wakeup_processor, ProcessorInterface)
        assert wakeup_processor.startup_channel_id == "test_channel"
        assert wakeup_processor.agent_profile.name == "TestAgent"
        assert not wakeup_processor.wakeup_complete
    
    def test_get_supported_states(self, wakeup_processor):
        """Test WakeupProcessor supports only WAKEUP state."""
        supported = wakeup_processor.get_supported_states()
        assert supported == [AgentState.WAKEUP]
    
    @pytest.mark.asyncio
    async def test_can_process(self, wakeup_processor):
        """Test WakeupProcessor can_process method."""
        assert await wakeup_processor.can_process(AgentState.WAKEUP)
        assert not await wakeup_processor.can_process(AgentState.WORK)
        assert not await wakeup_processor.can_process(AgentState.PLAY)
    
    @pytest.mark.asyncio
    async def test_process_method(self, wakeup_processor):
        """Test WakeupProcessor process method."""
        with patch.object(wakeup_processor, '_process_wakeup') as mock_process_wakeup:
            mock_process_wakeup.return_value = {"status": "in_progress", "wakeup_complete": False}
            
            result = await wakeup_processor.process(0)
            
            assert isinstance(result, dict)
            mock_process_wakeup.assert_called_once_with(0, non_blocking=True)
    
    def test_get_status(self, wakeup_processor):
        """Test WakeupProcessor get_status method."""
        status = wakeup_processor.get_status()
        
        assert isinstance(status, dict)
        assert status["processor_type"] == "wakeup"
        assert "wakeup_complete" in status
        assert "progress" in status
    
    @pytest.mark.asyncio
    async def test_start_processing(self, wakeup_processor):
        """Test WakeupProcessor start_processing method."""
        with patch.object(wakeup_processor, 'process') as mock_process:
            mock_process.return_value = {"wakeup_complete": True}
            
            # Test with limited rounds
            await wakeup_processor.start_processing(num_rounds=1)
            
            mock_process.assert_called()
    
    @pytest.mark.asyncio
    async def test_stop_processing(self, wakeup_processor):
        """Test WakeupProcessor stop_processing method."""
        await wakeup_processor.stop_processing()
        assert wakeup_processor.wakeup_complete


class TestWorkProcessor:
    """Comprehensive tests for WorkProcessor."""
    
    @pytest.fixture
    def work_processor(self, mock_config, mock_thought_processor, mock_action_dispatcher, mock_services):
        return WorkProcessor(
            app_config=mock_config,
            thought_processor=mock_thought_processor,
            action_dispatcher=mock_action_dispatcher,
            services=mock_services,
            startup_channel_id="test_channel"
        )
    
    def test_work_processor_initialization(self, work_processor):
        """Test WorkProcessor initializes correctly."""
        assert isinstance(work_processor, WorkProcessor)
        assert isinstance(work_processor, ProcessorInterface)
        assert work_processor.startup_channel_id == "test_channel"
        assert hasattr(work_processor, 'task_manager')
        assert hasattr(work_processor, 'thought_manager')
    
    def test_get_supported_states(self, work_processor):
        """Test WorkProcessor supports WORK and PLAY states."""
        supported = work_processor.get_supported_states()
        assert AgentState.WORK in supported
        assert AgentState.PLAY in supported
    
    @pytest.mark.asyncio
    async def test_can_process(self, work_processor):
        """Test WorkProcessor can_process method."""
        assert await work_processor.can_process(AgentState.WORK)
        assert await work_processor.can_process(AgentState.PLAY)
        assert not await work_processor.can_process(AgentState.WAKEUP)
        assert not await work_processor.can_process(AgentState.SOLITUDE)
    
    @pytest.mark.asyncio
    async def test_process_method(self, work_processor):
        """Test WorkProcessor process method."""
        with patch.object(work_processor.task_manager, 'activate_pending_tasks', return_value=0), \
             patch.object(work_processor.task_manager, 'get_tasks_needing_seed', return_value=[]), \
             patch.object(work_processor.thought_manager, 'generate_seed_thoughts', return_value=0), \
             patch.object(work_processor.thought_manager, 'populate_queue', return_value=0), \
             patch.object(work_processor, '_handle_idle_state'):
            
            result = await work_processor.process(1)
            
            assert isinstance(result, dict)
            assert "round_number" in result
            assert "was_idle" in result
    
    def test_get_status(self, work_processor):
        """Test WorkProcessor get_status method."""
        status = work_processor.get_status()
        
        assert isinstance(status, dict)
        assert status["processor_type"] == "work"
        assert "work_stats" in status
    
    @pytest.mark.asyncio
    async def test_start_processing(self, work_processor):
        """Test WorkProcessor start_processing method."""
        with patch.object(work_processor, 'process') as mock_process:
            mock_process.return_value = {"round_number": 1}
            
            # Start in background and stop immediately
            task = asyncio.create_task(work_processor.start_processing(num_rounds=1))
            await asyncio.sleep(0.01)  # Let it start
            await work_processor.stop_processing()
            
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except asyncio.TimeoutError:
                task.cancel()
    
    @pytest.mark.asyncio
    async def test_stop_processing(self, work_processor):
        """Test WorkProcessor stop_processing method."""
        await work_processor.stop_processing()
        assert not getattr(work_processor, '_running', True)


class TestPlayProcessor:
    """Comprehensive tests for PlayProcessor."""
    
    @pytest.fixture
    def play_processor(self, mock_config, mock_thought_processor, mock_action_dispatcher, mock_services):
        return PlayProcessor(
            app_config=mock_config,
            thought_processor=mock_thought_processor,
            action_dispatcher=mock_action_dispatcher,
            services=mock_services
        )
    
    def test_play_processor_initialization(self, play_processor):
        """Test PlayProcessor initializes correctly."""
        assert isinstance(play_processor, PlayProcessor)
        assert isinstance(play_processor, ProcessorInterface)
        assert hasattr(play_processor, 'play_metrics')
        assert "creative_tasks_processed" in play_processor.play_metrics
    
    def test_get_supported_states(self, play_processor):
        """Test PlayProcessor supports only PLAY state."""
        supported = play_processor.get_supported_states()
        assert supported == [AgentState.PLAY]
    
    @pytest.mark.asyncio
    async def test_process_method(self, play_processor):
        """Test PlayProcessor process method."""
        with patch('ciris_engine.processor.work_processor.WorkProcessor.process') as mock_super_process:
            mock_super_process.return_value = {"thoughts_processed": 3}
            
            result = await play_processor.process(1)
            
            assert isinstance(result, dict)
            assert result["mode"] == "play"
            assert result["creativity_enabled"] is True
            assert play_processor.play_metrics["creative_tasks_processed"] == 3
    
    def test_get_status(self, play_processor):
        """Test PlayProcessor get_status method."""
        with patch('ciris_engine.processor.work_processor.WorkProcessor.get_status') as mock_super_status:
            mock_super_status.return_value = {"processor_type": "work"}
            
            status = play_processor.get_status()
            
            assert isinstance(status, dict)
            assert status["processor_type"] == "play"
            assert "play_stats" in status
            assert "creativity_level" in status
    
    def test_creativity_level_calculation(self, play_processor):
        """Test creativity level calculation."""
        # Test with no tasks processed
        assert play_processor._calculate_creativity_level() == 0.0
        
        # Test with some metrics
        play_processor.play_metrics["creative_tasks_processed"] = 10
        play_processor.play_metrics["experiments_run"] = 3
        play_processor.play_metrics["novel_approaches_tried"] = 2
        
        creativity = play_processor._calculate_creativity_level()
        assert 0.0 <= creativity <= 1.0


class TestSolitudeProcessor:
    """Comprehensive tests for SolitudeProcessor."""
    
    @pytest.fixture
    def solitude_processor(self, mock_config, mock_thought_processor, mock_action_dispatcher, mock_services):
        return SolitudeProcessor(
            app_config=mock_config,
            thought_processor=mock_thought_processor,
            action_dispatcher=mock_action_dispatcher,
            services=mock_services,
            critical_priority_threshold=8
        )
    
    def test_solitude_processor_initialization(self, solitude_processor):
        """Test SolitudeProcessor initializes correctly."""
        assert isinstance(solitude_processor, SolitudeProcessor)
        assert isinstance(solitude_processor, ProcessorInterface)
        assert solitude_processor.critical_priority_threshold == 8
        assert hasattr(solitude_processor, 'reflection_data')
    
    def test_get_supported_states(self, solitude_processor):
        """Test SolitudeProcessor supports only SOLITUDE state."""
        supported = solitude_processor.get_supported_states()
        assert supported == [AgentState.SOLITUDE]
    
    @pytest.mark.asyncio
    async def test_can_process(self, solitude_processor):
        """Test SolitudeProcessor can_process method."""
        assert await solitude_processor.can_process(AgentState.SOLITUDE)
        assert not await solitude_processor.can_process(AgentState.WORK)
    
    @pytest.mark.asyncio
    async def test_process_method(self, solitude_processor):
        """Test SolitudeProcessor process method."""
        with patch.object(solitude_processor, '_check_critical_tasks', return_value=0), \
             patch.object(solitude_processor, '_check_exit_conditions', 
                         return_value={"should_exit": False, "reason": None}):
            
            result = await solitude_processor.process(1)
            
            assert isinstance(result, dict)
            assert "round_number" in result
            assert "critical_tasks_found" in result
            assert "should_exit_solitude" in result
    
    def test_get_status(self, solitude_processor):
        """Test SolitudeProcessor get_status method."""
        status = solitude_processor.get_status()
        
        assert isinstance(status, dict)
        assert status["processor_type"] == "solitude"
        assert "solitude_stats" in status
        assert "critical_threshold" in status
    
    @pytest.mark.asyncio
    async def test_start_processing(self, solitude_processor):
        """Test SolitudeProcessor start_processing method."""
        with patch.object(solitude_processor, 'process') as mock_process:
            mock_process.return_value = {"should_exit_solitude": True, "exit_reason": "test"}
            
            # Test with limited rounds
            await solitude_processor.start_processing(num_rounds=1)
            
            mock_process.assert_called()
    
    @pytest.mark.asyncio
    async def test_stop_processing(self, solitude_processor):
        """Test SolitudeProcessor stop_processing method."""
        await solitude_processor.stop_processing()
        assert not getattr(solitude_processor, '_running', True)


class TestDreamProcessor:
    """Comprehensive tests for DreamProcessor."""
    
    @pytest.fixture
    def dream_processor(self, mock_config, mock_profile):
        return DreamProcessor(
            app_config=mock_config,
            profile=mock_profile,
            service_registry=None,
            cirisnode_url="http://test:8001"
        )
    
    def test_dream_processor_initialization(self, dream_processor):
        """Test DreamProcessor initializes correctly."""
        assert isinstance(dream_processor, DreamProcessor)
        assert dream_processor.cirisnode_url == "http://test:8001"
        assert hasattr(dream_processor, 'dream_metrics')
        assert "total_pulses" in dream_processor.dream_metrics
    
    @pytest.mark.asyncio
    async def test_start_dreaming(self, dream_processor):
        """Test DreamProcessor start_dreaming method."""
        with patch.object(dream_processor, '_dream_loop') as mock_dream_loop:
            mock_dream_loop.return_value = None
            
            await dream_processor.start_dreaming(duration=1.0)
            
            assert dream_processor.dream_metrics["total_dreams"] == 1
            assert dream_processor._dream_task is not None
    
    @pytest.mark.asyncio
    async def test_stop_dreaming(self, dream_processor):
        """Test DreamProcessor stop_dreaming method."""
        # Start dreaming first
        with patch.object(dream_processor, '_dream_loop'):
            await dream_processor.start_dreaming(duration=0.1)
            await asyncio.sleep(0.01)  # Let it start
            
            await dream_processor.stop_dreaming()
            
            assert dream_processor.dream_metrics.get("end_time") is not None
    
    def test_get_dream_summary(self, dream_processor):
        """Test DreamProcessor get_dream_summary method."""
        summary = dream_processor.get_dream_summary()
        
        assert isinstance(summary, dict)
        assert "state" in summary
        assert "metrics" in summary
        assert "recent_snores" in summary
    
    def test_should_enter_dream_state(self, dream_processor):
        """Test dream state recommendation logic."""
        # Test below threshold
        assert not dream_processor.should_enter_dream_state(100, min_idle_threshold=300)
        
        # Test above threshold
        assert dream_processor.should_enter_dream_state(400, min_idle_threshold=300)


class TestAgentProcessor:
    """Comprehensive tests for AgentProcessor (main processor)."""
    
    @pytest.fixture
    def agent_processor(self, mock_config, mock_profile, mock_thought_processor, 
                       mock_action_dispatcher, mock_services):
        processor = AgentProcessor(
            app_config=mock_config,
            active_profile=mock_profile,
            thought_processor=mock_thought_processor,
            action_dispatcher=mock_action_dispatcher,
            services=mock_services,
            startup_channel_id="test_channel"
        )
        # Mock the state manager
        processor.state_manager = MockStateManager()
        return processor
    
    def test_agent_processor_initialization(self, agent_processor):
        """Test AgentProcessor initializes correctly."""
        assert isinstance(agent_processor, AgentProcessor)
        assert isinstance(agent_processor, ProcessorInterface)
        assert agent_processor.startup_channel_id == "test_channel"
        assert hasattr(agent_processor, 'wakeup_processor')
        assert hasattr(agent_processor, 'work_processor')
        assert hasattr(agent_processor, 'play_processor')
        assert hasattr(agent_processor, 'solitude_processor')
    
    @pytest.mark.asyncio
    async def test_process_method(self, agent_processor):
        """Test AgentProcessor process method delegates to appropriate processor."""
        # Test WAKEUP state
        agent_processor.state_manager.current_state = AgentState.WAKEUP
        with patch.object(agent_processor.wakeup_processor, 'process') as mock_process:
            mock_process.return_value = {"state": "wakeup", "round": 1}
            
            result = await agent_processor.process(1)
            assert result["state"] == "wakeup"
            mock_process.assert_called_once_with(1)
        
        # Test WORK state
        agent_processor.state_manager.current_state = AgentState.WORK
        with patch.object(agent_processor.work_processor, 'process') as mock_process:
            mock_process.return_value = {"state": "work", "round": 1}
            
            result = await agent_processor.process(1)
            assert result["state"] == "work"
            mock_process.assert_called_once_with(1)
    
    def test_get_status(self, agent_processor):
        """Test AgentProcessor get_status method."""
        agent_processor.state_manager.current_state = AgentState.WORK
        
        with patch.object(agent_processor.work_processor, 'get_status') as mock_status:
            mock_status.return_value = {"processor_type": "work", "active_tasks": 5}
            
            status = agent_processor.get_status()
            
            assert isinstance(status, dict)
            assert "state" in status
            assert "round_number" in status
            assert "work_status" in status
    
    @pytest.mark.asyncio
    async def test_start_processing(self, agent_processor):
        """Test AgentProcessor start_processing method."""
        with patch.object(agent_processor.wakeup_processor, 'initialize'), \
             patch.object(agent_processor.wakeup_processor, 'process') as mock_process, \
             patch.object(agent_processor, '_process_pending_thoughts_async', return_value=0):
            
            mock_process.return_value = {"wakeup_complete": True}
            
            # Mock state transitions
            agent_processor.state_manager.transition_to = MagicMock(return_value=True)
            
            # Test with limited rounds to avoid infinite loop
            await agent_processor.start_processing(num_rounds=1)
            
            mock_process.assert_called()
    
    @pytest.mark.asyncio
    async def test_stop_processing(self, agent_processor):
        """Test AgentProcessor stop_processing method."""
        # Mock processors
        for processor in agent_processor.state_processors.values():
            processor.cleanup = AsyncMock()
        
        await agent_processor.stop_processing()
        
        assert agent_processor.state_manager.get_state() == AgentState.SHUTDOWN


class TestProcessorIntegration:
    """Integration tests for processor interactions."""
    
    @pytest.mark.asyncio
    async def test_state_transition_flow(self):
        """Test typical state transition flow through processors."""
        # This would test a full flow from WAKEUP -> WORK -> PLAY -> SOLITUDE
        # Mock the necessary components for integration testing
        pass
    
    @pytest.mark.asyncio
    async def test_processor_error_handling(self):
        """Test error handling across different processors."""
        # Test that processors handle errors gracefully
        pass
    
    def test_processor_metrics_consistency(self):
        """Test that all processors provide consistent metrics structure."""
        # Verify all processors return compatible status structures
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])