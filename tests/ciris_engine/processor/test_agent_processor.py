"""
Tests for AgentProcessor focusing on ProcessorInterface compliance and core functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from ciris_engine.processor.main_processor import AgentProcessor
from ciris_engine.protocols.processor_interface import ProcessorInterface
from ciris_engine.schemas.config_schemas_v1 import AppConfig, AgentProfile
from ciris_engine.schemas.states_v1 import AgentState


class TestAgentProcessorProtocolCompliance:
    """Test that AgentProcessor properly implements ProcessorInterface."""

    @pytest.fixture
    def minimal_config(self):
        """Create minimal config for testing."""
        config = MagicMock(spec=AppConfig)
        config.agent_mode = "cli"
        config.max_thoughts_per_round = 5
        config.processing_delay_ms = 100
        config.workflow = MagicMock()
        return config

    @pytest.fixture
    def minimal_profile(self):
        """Create minimal profile for testing."""
        return AgentProfile(name="test_profile")

    @pytest.fixture
    def mock_dependencies(self):
        """Create all mock dependencies needed for AgentProcessor."""
        return {
            "thought_processor": AsyncMock(),
            "action_dispatcher": AsyncMock(),
            "services": {"test": AsyncMock()}
        }

    @pytest.fixture
    def agent_processor(self, minimal_config, minimal_profile, mock_dependencies):
        """Create AgentProcessor with mocked sub-processors."""
        with patch('ciris_engine.processor.main_processor.WakeupProcessor'), \
             patch('ciris_engine.processor.main_processor.WorkProcessor'), \
             patch('ciris_engine.processor.main_processor.PlayProcessor'), \
             patch('ciris_engine.processor.main_processor.SolitudeProcessor'), \
             patch('ciris_engine.processor.main_processor.DreamProcessor'), \
             patch('ciris_engine.processor.main_processor.persistence'):
            
            processor = AgentProcessor(
                app_config=minimal_config,
                active_profile=minimal_profile,
                thought_processor=mock_dependencies["thought_processor"],
                action_dispatcher=mock_dependencies["action_dispatcher"],
                services=mock_dependencies["services"]
            )
            
            # Mock all sub-processor methods that get called
            processor.wakeup_processor.initialize = AsyncMock()
            processor.wakeup_processor.process_wakeup = AsyncMock(return_value={"wakeup_complete": True})
            processor.work_processor.initialize = AsyncMock()
            processor.dream_processor.stop_dreaming = AsyncMock()
            
            # Mock state processors cleanup
            for state_processor in processor.state_processors.values():
                state_processor.cleanup = AsyncMock()
            
            # Mock the processing loop to prevent it from running
            processor._processing_loop = AsyncMock()
            
            return processor

    def test_implements_processor_interface(self, agent_processor):
        """Test that AgentProcessor implements ProcessorInterface."""
        assert isinstance(agent_processor, ProcessorInterface)
        
        # Check that required methods exist
        assert hasattr(agent_processor, 'start_processing')
        assert hasattr(agent_processor, 'stop_processing')
        assert hasattr(agent_processor, 'get_status')
        
        # Check method signatures
        import inspect
        
        start_sig = inspect.signature(agent_processor.start_processing)
        assert 'num_rounds' in start_sig.parameters
        
        stop_sig = inspect.signature(agent_processor.stop_processing)
        assert len(stop_sig.parameters) == 0  # Should take no parameters
        
        status_sig = inspect.signature(agent_processor.get_status)
        assert len(status_sig.parameters) == 0  # Should take no parameters

    @pytest.mark.asyncio
    async def test_start_processing_interface_compliance(self, agent_processor):
        """Test start_processing method compliance with interface."""
        with patch.object(agent_processor.state_manager, 'transition_to', return_value=True):
            # Should accept no arguments (defaults to None)
            await agent_processor.start_processing()
            
            # Should accept num_rounds parameter
            await agent_processor.start_processing(num_rounds=5)

    @pytest.mark.asyncio
    async def test_stop_processing_interface_compliance(self, agent_processor):
        """Test stop_processing method compliance with interface."""
        # Test case 1: No running task - should return gracefully
        await agent_processor.stop_processing()
        
        # Stop event should NOT be set when there's no running task
        assert not agent_processor._stop_event.is_set()
        
        # Test case 2: Create an actual task to mock a running processing task
        import asyncio
        
        async def dummy_coroutine():
            await asyncio.sleep(0.1)
        
        # Create an actual task
        mock_task = asyncio.create_task(dummy_coroutine())
        agent_processor._processing_task = mock_task
        
        # Should be callable without arguments
        await agent_processor.stop_processing()
        
        # Should set the stop event when there's a running task
        assert agent_processor._stop_event.is_set()

    def test_get_status_interface_compliance(self, agent_processor):
        """Test get_status method compliance with interface."""
        with patch('ciris_engine.persistence.count_thoughts', return_value=10):
            with patch('ciris_engine.persistence.count_tasks', return_value=3):
                status = agent_processor.get_status()
                
                # Should return a dictionary
                assert isinstance(status, dict)
                
                # Should contain expected status fields
                assert "state" in status
                assert "round_number" in status
                assert "is_processing" in status

    @pytest.mark.asyncio
    async def test_start_processing_state_transition(self, agent_processor):
        """Test that start_processing properly transitions to WAKEUP state."""
        with patch.object(agent_processor.state_manager, 'transition_to', return_value=True) as mock_transition:
            # Mock wakeup completion to avoid full processing
            agent_processor.wakeup_processor.process_wakeup = AsyncMock(return_value={"wakeup_complete": True})
            
            await agent_processor.start_processing()
            
            # Check that WAKEUP transition was called (first call)
            assert mock_transition.call_count >= 1
            first_call = mock_transition.call_args_list[0]
            assert first_call[0][0] == AgentState.WAKEUP

    @pytest.mark.asyncio
    async def test_start_processing_handles_transition_failure(self, agent_processor):
        """Test start_processing handles state transition failure gracefully."""
        with patch.object(agent_processor.state_manager, 'transition_to', return_value=False):
            with patch.object(agent_processor.wakeup_processor, 'initialize') as mock_init:
                await agent_processor.start_processing()
                
                # Should not initialize if transition fails
                mock_init.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_start_processing_initializes_wakeup_processor(self, agent_processor):
        """Test that start_processing initializes the wakeup processor."""
        with patch.object(agent_processor.state_manager, 'transition_to', return_value=True):
            await agent_processor.start_processing()
            
            agent_processor.wakeup_processor.initialize.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_multiple_start_processing_calls(self, agent_processor):
        """Test that multiple start_processing calls are handled properly."""
        # Mock a running task - use MagicMock for the done() method
        from unittest.mock import MagicMock
        agent_processor._processing_task = MagicMock()
        agent_processor._processing_task.done.return_value = False
        
        # First call should return early due to already running task
        await agent_processor.start_processing()
        
        # Verify it returned early by checking that wakeup processor wasn't called
        agent_processor.wakeup_processor.initialize.assert_not_awaited()

    def test_property_access(self, agent_processor, mock_dependencies):
        """Test property access works correctly."""
        # Test action_dispatcher property
        assert agent_processor.action_dispatcher == mock_dependencies["action_dispatcher"]
        
        # Test that we can set a new dispatcher
        new_dispatcher = AsyncMock()
        agent_processor.action_dispatcher = new_dispatcher
        assert agent_processor.action_dispatcher == new_dispatcher

    def test_initialization_creates_required_components(self, agent_processor):
        """Test that initialization creates all required components."""
        # Should have state manager
        assert hasattr(agent_processor, 'state_manager')
        
        # Should have all sub-processors
        assert hasattr(agent_processor, 'wakeup_processor')
        assert hasattr(agent_processor, 'work_processor')
        assert hasattr(agent_processor, 'play_processor')
        assert hasattr(agent_processor, 'solitude_processor')
        assert hasattr(agent_processor, 'dream_processor')
        
        # Should have processing control attributes
        assert hasattr(agent_processor, 'current_round_number')
        assert hasattr(agent_processor, '_stop_event')
        assert hasattr(agent_processor, '_processing_task')

    def test_round_number_initialization(self, agent_processor):
        """Test that round number starts at 0."""
        assert agent_processor.current_round_number == 0

    @pytest.mark.asyncio
    async def test_stop_event_behavior(self, agent_processor):
        """Test stop event behavior."""
        # Initially should not be set
        assert not agent_processor._stop_event.is_set()
        
        # Create a running task to trigger stop event
        import asyncio
        
        async def dummy_coroutine():
            await asyncio.sleep(0.1)
        
        # Create an actual task
        mock_task = asyncio.create_task(dummy_coroutine())
        agent_processor._processing_task = mock_task
        
        # After stop_processing with running task, should be set
        await agent_processor.stop_processing()
        assert agent_processor._stop_event.is_set()

    def test_processor_interface_abstract_methods_implemented(self):
        """Test that all abstract methods from ProcessorInterface are implemented."""
        from ciris_engine.protocols.processor_interface import ProcessorInterface
        import inspect
        
        # Get all abstract methods from the interface
        abstract_methods = []
        for name, method in inspect.getmembers(ProcessorInterface, predicate=inspect.isfunction):
            if getattr(method, '__isabstractmethod__', False):
                abstract_methods.append(name)
        
        # Verify AgentProcessor implements all abstract methods
        for method_name in abstract_methods:
            assert hasattr(AgentProcessor, method_name), f"AgentProcessor missing abstract method: {method_name}"
            
            # Verify it's not still abstract
            method = getattr(AgentProcessor, method_name)
            assert not getattr(method, '__isabstractmethod__', False), f"Method {method_name} is still abstract"