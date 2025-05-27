"""
Main agent processor that coordinates all processing activities.
Uses v1 schemas and integrates state management.
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from ciris_engine.schemas.config_schemas_v1 import AppConfig
from ciris_engine.schemas.states import AgentState

from ciris_engine.core.workflow_coordinator import WorkflowCoordinator
from ciris_engine.core.action_dispatcher import ActionDispatcher

from .state_manager import StateManager
from .wakeup_processor import WakeupProcessor
from .work_processor import WorkProcessor
from .play_processor import PlayProcessor
from .dream_processor import DreamProcessor
from .solitude_processor import SolitudeProcessor

logger = logging.getLogger(__name__)


class AgentProcessor:
    """
    Main agent processor that orchestrates task processing, thought generation,
    and state management using v1 schemas.
    """
    
    def __init__(
        self,
        app_config: AppConfig,
        workflow_coordinator: WorkflowCoordinator,
        action_dispatcher: ActionDispatcher,
        services: Dict[str, Any],
        startup_channel_id: Optional[str] = None,
    ):
        """Initialize the agent processor with v1 configuration."""
        self.app_config = app_config
        self.workflow_coordinator = workflow_coordinator
        self.action_dispatcher = action_dispatcher
        self.services = services
        self.startup_channel_id = startup_channel_id
        
        # Initialize state manager
        self.state_manager = StateManager(initial_state=AgentState.SHUTDOWN)
        
        # Initialize specialized processors
        self.wakeup_processor = WakeupProcessor(
            app_config=app_config,
            workflow_coordinator=workflow_coordinator,
            action_dispatcher=action_dispatcher,
            services=services,
            startup_channel_id=startup_channel_id
        )
        
        self.work_processor = WorkProcessor(
            app_config=app_config,
            workflow_coordinator=workflow_coordinator,
            action_dispatcher=action_dispatcher,
            services=services
        )
        
        self.play_processor = PlayProcessor(
            app_config=app_config,
            workflow_coordinator=workflow_coordinator,
            action_dispatcher=action_dispatcher,
            services=services
        )
        
        self.solitude_processor = SolitudeProcessor(
            app_config=app_config,
            workflow_coordinator=workflow_coordinator,
            action_dispatcher=action_dispatcher,
            services=services
        )
        
        self.dream_processor = DreamProcessor(
            cirisnode_url=app_config.cirisnode.base_url if hasattr(app_config, 'cirisnode') else "http://localhost:8001"
        )
        
        # Map states to processors
        self.state_processors = {
            AgentState.WAKEUP: self.wakeup_processor,
            AgentState.WORK: self.work_processor,
            AgentState.PLAY: self.play_processor,
            AgentState.SOLITUDE: self.solitude_processor,
            # DREAM is handled separately
            # SHUTDOWN has no processor
        }
        
        # Processing control
        self.current_round_number = 0
        self._stop_event = asyncio.Event()
        self._processing_task: Optional[asyncio.Task] = None
        
        logger.info("AgentProcessor initialized with v1 schemas and modular processors")
    
    async def start_processing(self, num_rounds: Optional[int] = None):
        """Start the main agent processing loop."""
        if self._processing_task and not self._processing_task.done():
            logger.warning("Processing is already running")
            return
        
        self._stop_event.clear()
        logger.info(f"Starting agent processing (rounds: {num_rounds or 'infinite'})")
        
        # Transition to WAKEUP state
        if not self.state_manager.transition_to(AgentState.WAKEUP):
            logger.error("Failed to transition to WAKEUP state")
            return
        
        # Initialize wakeup processor
        await self.wakeup_processor.initialize()
        
        # Run wakeup sequence
        wakeup_result = await self.wakeup_processor.process(self.current_round_number)
        
        if wakeup_result.get("status") != "success":
            logger.error(f"Wakeup sequence failed: {wakeup_result.get('error')}")
            await self.stop_processing()
            return
        
        # Transition to WORK state
        if not self.state_manager.transition_to(AgentState.WORK):
            logger.error("Failed to transition to WORK state after wakeup")
            await self.stop_processing()
            return
        
        # Initialize work processor
        await self.work_processor.initialize()
        
        # Start main processing loop
        self._processing_task = asyncio.create_task(self._processing_loop(num_rounds))
        
        try:
            await self._processing_task
        except asyncio.CancelledError:
            logger.info("Processing task was cancelled")
        except Exception as e:
            logger.error(f"Processing loop error: {e}", exc_info=True)
        finally:
            self._stop_event.set()
    
    async def stop_processing(self):
        """Stop the processing loop gracefully."""
        if not self._processing_task or self._processing_task.done():
            logger.info("Processing loop is not running")
            return
        
        logger.info("Stopping processing loop...")
        self._stop_event.set()
        
        # Stop dream if active
        if self.state_manager.get_state() == AgentState.DREAM:
            await self.dream_processor.stop_dreaming()
        
        # Clean up processors
        for processor in self.state_processors.values():
            try:
                await processor.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up {processor}: {e}")
        
        # Transition to SHUTDOWN
        self.state_manager.transition_to(AgentState.SHUTDOWN)
        
        try:
            await asyncio.wait_for(self._processing_task, timeout=10.0)
            logger.info("Processing loop stopped")
        except asyncio.TimeoutError:
            logger.warning("Processing loop did not stop within timeout, cancelling")
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                logger.info("Processing task cancelled")
        finally:
            self._processing_task = None
    
    async def _processing_loop(self, num_rounds: Optional[int] = None):
        """Main processing loop with state management."""
        round_count = 0
        
        while not self._stop_event.is_set():
            if num_rounds is not None and round_count >= num_rounds:
                logger.info(f"Reached target rounds ({num_rounds})")
                break
            
            # Update round number
            self.workflow_coordinator.advance_round()
            self.current_round_number = self.workflow_coordinator.current_round_number
            
            # Check for automatic state transitions
            next_state = self.state_manager.should_auto_transition()
            if next_state:
                await self._handle_state_transition(next_state)
            
            # Process based on current state
            current_state = self.state_manager.get_state()
            
            # Get processor for current state
            processor = self.state_processors.get(current_state)
            
            if processor:
                # Use the appropriate processor
                try:
                    result = await processor.process(self.current_round_number)
                    round_count += 1
                    
                    # Check for state transition recommendations
                    if current_state == AgentState.WORK:
                        if self.work_processor.should_transition_to_dream():
                            await self._handle_state_transition(AgentState.DREAM)
                    
                    elif current_state == AgentState.SOLITUDE and processor == self.solitude_processor:
                        if result.get("should_exit_solitude"):
                            logger.info(f"Exiting solitude: {result.get('exit_reason', 'Unknown reason')}")
                            await self._handle_state_transition(AgentState.WORK)
                            
                except Exception as e:
                    logger.error(f"Error in {processor} for state {current_state}: {e}", exc_info=True)
                    
            elif current_state == AgentState.DREAM:
                # Dream processing is handled by dream_processor
                await asyncio.sleep(5)  # Check periodically
                
            elif current_state == AgentState.SHUTDOWN:
                # In shutdown state, exit the loop
                logger.info("In SHUTDOWN state, exiting processing loop")
                break
                
            else:
                logger.warning(f"No processor for state: {current_state}")
                await asyncio.sleep(1)
            
            # Brief delay between rounds
            delay = 1.0  # TODO: Get from config
            
            # Longer delay for certain states
            if current_state == AgentState.SOLITUDE:
                delay = 10.0  # Slower pace in solitude
            elif current_state == AgentState.DREAM:
                delay = 5.0  # Check dream state periodically
            
            if delay > 0 and not self._stop_event.is_set():
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
                    break  # Stop event was set
                except asyncio.TimeoutError:
                    pass  # Continue processing
        
        logger.info("Processing loop finished")
    
    async def _handle_state_transition(self, target_state: AgentState):
        """Handle transitioning to a new state."""
        current_state = self.state_manager.get_state()
        
        if not self.state_manager.transition_to(target_state):
            logger.error(f"Failed to transition from {current_state} to {target_state}")
            return
        
        # Handle state-specific initialization/cleanup
        if target_state == AgentState.DREAM:
            # Start dream processing
            duration = 600  # 10 minutes, TODO: make configurable
            await self.dream_processor.start_dreaming(duration)
            
        elif target_state == AgentState.WORK and current_state == AgentState.DREAM:
            # Stop dream processing
            await self.dream_processor.stop_dreaming()
            
            # Log dream summary
            summary = self.dream_processor.get_dream_summary()
            logger.info(f"Dream summary: {summary}")
            
        # Initialize processor if needed
        if target_state in self.state_processors:
            processor = self.state_processors[target_state]
            await processor.initialize()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current processor status."""
        status = {
            "state": self.state_manager.get_state().value,
            "state_duration": self.state_manager.get_state_duration(),
            "round_number": self.current_round_number,
            "is_processing": self._processing_task is not None and not self._processing_task.done(),
        }
        
        # Add state-specific status
        current_state = self.state_manager.get_state()
        
        if current_state == AgentState.WAKEUP:
            status["wakeup_progress"] = self.wakeup_processor.get_wakeup_progress()
            
        elif current_state == AgentState.WORK:
            status.update(self.work_processor.get_work_stats())
            
        elif current_state == AgentState.PLAY:
            status.update(self.play_processor.get_play_stats())
            
        elif current_state == AgentState.SOLITUDE:
            status["solitude_stats"] = self.solitude_processor.get_solitude_stats()
            
        elif current_state == AgentState.DREAM:
            status["dream_summary"] = self.dream_processor.get_dream_summary()
        
        # Add processor metrics
        status["processor_metrics"] = {}
        for state, processor in self.state_processors.items():
            status["processor_metrics"][state.value] = processor.get_metrics()
        
        return status