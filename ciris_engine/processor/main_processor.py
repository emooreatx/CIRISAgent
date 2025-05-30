"""
Main agent processor that coordinates all processing activities.
Uses v1 schemas and integrates state management.
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from datetime import datetime, timezone

from ciris_engine.schemas.config_schemas_v1 import AppConfig
from ciris_engine.schemas.states import AgentState
from ciris_engine import persistence
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, ThoughtStatus, Task
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.utils.context_utils import build_dispatch_context

from ciris_engine.processor.thought_processor import ThoughtProcessor
if TYPE_CHECKING:
    from ciris_engine.action_handlers.action_dispatcher import ActionDispatcher

# For main_processor.py and work_processor.py (or anywhere else you need it)
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
        thought_processor: ThoughtProcessor,
        action_dispatcher: "ActionDispatcher",
        services: Dict[str, Any],
        startup_channel_id: Optional[str] = None,
    ):
        """Initialize the agent processor with v1 configuration."""
        self.app_config = app_config
        self.thought_processor = thought_processor
        self._action_dispatcher = action_dispatcher  # Store internally
        self.services = services
        self.startup_channel_id = startup_channel_id
        
        # Initialize state manager
        self.state_manager = StateManager(initial_state=AgentState.SHUTDOWN)
        
        # Initialize specialized processors, passing the initial dispatcher
        self.wakeup_processor = WakeupProcessor(
            app_config=app_config,
            thought_processor=thought_processor,
            action_dispatcher=self._action_dispatcher, # Use internal dispatcher
            services=services,
            startup_channel_id=startup_channel_id
        )
        
        self.work_processor = WorkProcessor(
            app_config=app_config,
            thought_processor=thought_processor,
            action_dispatcher=self._action_dispatcher,  # Use internal dispatcher
            services=services,
            startup_channel_id=startup_channel_id,
        )
        
        self.play_processor = PlayProcessor(
            app_config=app_config,
            thought_processor=thought_processor,
            action_dispatcher=self._action_dispatcher, # Use internal dispatcher
            services=services
        )
        
        self.solitude_processor = SolitudeProcessor(
            app_config=app_config,
            thought_processor=thought_processor,
            action_dispatcher=self._action_dispatcher, # Use internal dispatcher
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

    @property
    def action_dispatcher(self) -> "ActionDispatcher":
        return self._action_dispatcher

    @action_dispatcher.setter
    def action_dispatcher(self, new_dispatcher: "ActionDispatcher"):
        logger.info(f"AgentProcessor's action_dispatcher is being updated to: {new_dispatcher}")
        self._action_dispatcher = new_dispatcher
        # Propagate the new dispatcher to sub-processors
        # Ensure sub-processors have an 'action_dispatcher' attribute to be updated
        sub_processors_to_update = [
            getattr(self, 'wakeup_processor', None),
            getattr(self, 'work_processor', None),
            getattr(self, 'play_processor', None),
            getattr(self, 'solitude_processor', None)
        ]
        for sub_processor in sub_processors_to_update:
            if sub_processor and hasattr(sub_processor, 'action_dispatcher'):
                logger.info(f"Updating action_dispatcher for {sub_processor.__class__.__name__}")
                sub_processor.action_dispatcher = new_dispatcher
            elif sub_processor:
                logger.warning(f"{sub_processor.__class__.__name__} does not have an 'action_dispatcher' attribute to update.")
        logger.info("AgentProcessor's action_dispatcher updated and propagated if applicable.")
    
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
        
        # Process WAKEUP in non-blocking mode
        wakeup_complete = False
        wakeup_round = 0
        max_wakeup_rounds = 30  # Safety limit
        
        while not wakeup_complete and not self._stop_event.is_set() and wakeup_round < max_wakeup_rounds:
            logger.info(f"=== WAKEUP Round {wakeup_round} ===")
            
            # 1. Run wakeup processor in non-blocking mode
            wakeup_result = await self.wakeup_processor.process_wakeup(wakeup_round, non_blocking=True)
            wakeup_complete = wakeup_result.get("wakeup_complete", False)
            
            if not wakeup_complete:
                # 2. Process any pending thoughts from ALL tasks (not just wakeup)
                # This ensures PONDER and other actions get processed
                thoughts_processed = await self._process_pending_thoughts_async()
                
                logger.info(f"Wakeup round {wakeup_round}: {wakeup_result.get('steps_completed', 0)}/{wakeup_result.get('total_steps', 5)} steps complete, {thoughts_processed} thoughts processed")
                
                # 3. Brief delay between rounds
                await asyncio.sleep(5.0)  # Increased delay for more natural pacing
            else:
                logger.info("✓ Wakeup sequence completed successfully!")
            
            wakeup_round += 1
            self.current_round_number += 1
        
        if not wakeup_complete:
            logger.error(f"Wakeup did not complete within {max_wakeup_rounds} rounds")
            await self.stop_processing()
            return
        
        # Transition to WORK state after wakeup completes
        if not self.state_manager.transition_to(AgentState.WORK):
            logger.error("Failed to transition to WORK state after wakeup")
            await self.stop_processing()
            return
        
        # Mark wakeup as complete in state metadata
        self.state_manager.update_state_metadata("wakeup_complete", True)
        
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

    async def _process_pending_thoughts_async(self) -> int:
        """
        Process all pending thoughts asynchronously.
        This is the key to non-blocking operation - it processes ALL thoughts,
        not just wakeup thoughts.
        """
        # Get all pending thoughts for active tasks
        pending_thoughts = persistence.get_pending_thoughts_for_active_tasks()
        
        # Apply max_active_thoughts limit from workflow config
        max_active = 10  # Default value
        if hasattr(self.app_config, 'workflow') and self.app_config.workflow:
            max_active = getattr(self.app_config.workflow, 'max_active_thoughts', 10)
        
        limited_thoughts = pending_thoughts[:max_active]
        
        logger.info(f"Found {len(pending_thoughts)} PENDING thoughts, processing {len(limited_thoughts)} (max_active_thoughts: {max_active})")
        
        if not limited_thoughts:
            return 0
        
        processed_count = 0
        
        # Process thoughts in parallel batches
        batch_size = 5  # Process up to 5 thoughts concurrently
        
        for i in range(0, len(limited_thoughts), batch_size):
            batch = limited_thoughts[i:i + batch_size]
            
            # Create tasks for parallel processing
            tasks = []
            for thought in batch:
                # Mark as PROCESSING
                persistence.update_thought_status(
                    thought_id=thought.thought_id,
                    status=ThoughtStatus.PROCESSING
                )
                
                # Create processing task
                task = self._process_single_thought(thought)
                tasks.append(task)
            
            # Wait for batch to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result, thought in zip(results, batch):
                if isinstance(result, Exception):
                    logger.error(f"Error processing thought {thought.thought_id}: {result}")
                    persistence.update_thought_status(
                        thought_id=thought.thought_id,
                        status=ThoughtStatus.FAILED,
                        final_action={"error": str(result)}
                    )
                else:
                    processed_count += 1
        
        return processed_count


    async def _process_single_thought(self, thought: Thought) -> bool:
        """Process a single thought and dispatch its action, with DMA fallback."""
        try:
            # Create processing queue item
            item = ProcessingQueueItem.from_thought(thought)

            # Use the current state's processor for fallback-aware processing
            processor = self.state_processors.get(self.state_manager.get_state())
            if processor is None:
                logger.error(f"No processor found for state {self.state_manager.get_state()}")
                return False

            # Use fallback-aware process_thought_item
            result = await processor.process_thought_item(item, context={"origin": "wakeup_async"})

            if result:
                # Get the task for context
                task = persistence.get_task_by_id(thought.source_task_id)
                dispatch_context = build_dispatch_context(
                    thought=thought, 
                    task=task, 
                    app_config=self.app_config, 
                    startup_channel_id=self.startup_channel_id, 
                    round_number=self.current_round_number
                )
                if hasattr(self, "discord_service"):
                    dispatch_context["discord_service"] = self.discord_service
                
                await self.action_dispatcher.dispatch(
                    action_selection_result=result,
                    thought=thought,
                    dispatch_context=dispatch_context
                )
                return True
            else:
                # Check if the thought was already handled (e.g., TASK_COMPLETE)
                updated_thought = persistence.get_thought_by_id(thought.thought_id)
                if updated_thought and updated_thought.status in [ThoughtStatus.COMPLETED, ThoughtStatus.FAILED]:
                    logger.debug(f"Thought {thought.thought_id} was already handled with status {updated_thought.status.value}")
                    return True
                else:
                    logger.warning(f"No result from processing thought {thought.thought_id}")
                    return False
        except Exception as e:
            logger.error(f"Error processing thought {thought.thought_id}: {e}", exc_info=True)
            raise
    
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
            # self.thought_processor.advance_round()  # Removed nonexistent method
            self.current_round_number += 1
            
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
