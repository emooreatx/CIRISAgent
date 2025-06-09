"""
Main agent processor that coordinates all processing activities.
Uses v1 schemas and integrates state management.
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from datetime import datetime, timezone

from ciris_engine.schemas.config_schemas_v1 import AppConfig, AgentProfile
from ciris_engine.schemas.states_v1 import AgentState
from ciris_engine import persistence
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, ThoughtStatus, Task
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.utils.context_utils import build_dispatch_context

from ciris_engine.processor.thought_processor import ThoughtProcessor
from ciris_engine.protocols.processor_interface import ProcessorInterface
if TYPE_CHECKING:
    from ciris_engine.action_handlers.action_dispatcher import ActionDispatcher

from .state_manager import StateManager
from .wakeup_processor import WakeupProcessor
from .work_processor import WorkProcessor
from .play_processor import PlayProcessor
from .dream_processor import DreamProcessor
from .solitude_processor import SolitudeProcessor

from ciris_engine.utils.shutdown_manager import request_global_shutdown

logger = logging.getLogger(__name__)


class AgentProcessor(ProcessorInterface):
    """
    Main agent processor that orchestrates task processing, thought generation,
    and state management using v1 schemas.
    """
    
    def __init__(
        self,
        app_config: AppConfig,
        active_profile: AgentProfile,
        thought_processor: ThoughtProcessor,
        action_dispatcher: "ActionDispatcher",
        services: Dict[str, Any],
        startup_channel_id: Optional[str] = None,
    ) -> None:
        """Initialize the agent processor with v1 configuration."""
        self.app_config = app_config
        self.active_profile = active_profile  # Store active profile
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
            startup_channel_id=startup_channel_id,
            agent_profile=active_profile
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
            app_config=app_config,  # Added
            profile=self.active_profile,  # Use the active profile directly
            service_registry=services.get("service_registry"),  # Pass service registry
            cirisnode_url=app_config.cirisnode.base_url if hasattr(app_config, 'cirisnode') else "https://localhost:8001"
        )
        
        # Map states to processors
        self.state_processors = {
            AgentState.WAKEUP: self.wakeup_processor,
            AgentState.WORK: self.work_processor,
            AgentState.PLAY: self.play_processor,
            AgentState.SOLITUDE: self.solitude_processor,
            # DREAM is handled separately TODO: Integrate DREAM state with processor
            # SHUTDOWN has no processor TODO: Turn graceful shutdown into a processor
        }
        
        # Processing control
        self.current_round_number = 0
        self._stop_event: Optional[asyncio.Event] = None
        self._processing_task: Optional[asyncio.Task] = None

        logger.info("AgentProcessor initialized with v1 schemas and modular processors")

    def _ensure_stop_event(self) -> None:
        """Ensure stop event is created when needed in async context."""
        if self._stop_event is None:
            try:
                self._stop_event = asyncio.Event()
            except RuntimeError:
                logger.warning("Cannot create stop event outside of async context")

    @property
    def action_dispatcher(self) -> "ActionDispatcher":
        return self._action_dispatcher

    @action_dispatcher.setter
    def action_dispatcher(self, new_dispatcher: "ActionDispatcher") -> None:
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
    
    async def start_processing(self, num_rounds: Optional[int] = None) -> None:
        """Start the main agent processing loop."""
        if self._processing_task and not self._processing_task.done():
            logger.warning("Processing is already running")
            return
        
        self._ensure_stop_event()
        if self._stop_event:
            self._stop_event.clear()
        logger.info(f"Starting agent processing (rounds: {num_rounds or 'infinite'})")
        
        if not self.state_manager.transition_to(AgentState.WAKEUP):
            logger.error("Failed to transition to WAKEUP state")
            return
        
        await self.wakeup_processor.initialize()
        
        wakeup_complete = False
        wakeup_round = 0
        
        while not wakeup_complete and not (self._stop_event and self._stop_event.is_set()) and (num_rounds is None or self.current_round_number < num_rounds):
            logger.info(f"=== WAKEUP Round {wakeup_round} ===")
            
            wakeup_result = await self.wakeup_processor.process(wakeup_round)
            wakeup_complete = wakeup_result.get("wakeup_complete", False)
            
            if not wakeup_complete:
                thoughts_processed = await self._process_pending_thoughts_async()
                
                logger.info(f"Wakeup round {wakeup_round}: {wakeup_result.get('steps_completed', 0)}/{wakeup_result.get('total_steps', 5)} steps complete, {thoughts_processed} thoughts processed")
                
                await asyncio.sleep(5.0)
            else:
                logger.info("✓ Wakeup sequence completed successfully!")
            
            wakeup_round += 1
            self.current_round_number += 1
        
        if not wakeup_complete:
            logger.error(f"Wakeup did not complete within {num_rounds or 'infinite'} rounds")
            await self.stop_processing()
            return
        
        if not self.state_manager.transition_to(AgentState.WORK):
            logger.error("Failed to transition to WORK state after wakeup")
            await self.stop_processing()
            return

        self.state_manager.update_state_metadata("wakeup_complete", True)

        if hasattr(self, "runtime") and hasattr(self.runtime, "start_interactive_console"):
            print("[STATE] Initializing interactive console for user input...")
            try:
                await self.runtime.start_interactive_console()
            except Exception as e:
                logger.error(f"Error initializing interactive console: {e}")

        await self.work_processor.initialize()
        
        self._processing_task = asyncio.create_task(self._processing_loop(num_rounds))
        
        try:
            await self._processing_task
        except asyncio.CancelledError:
            logger.info("Processing task was cancelled")
        except Exception as e:
            logger.error(f"Processing loop error: {e}", exc_info=True)
        finally:
            if self._stop_event:
                self._stop_event.set()

    async def _process_pending_thoughts_async(self) -> int:
        """
        Process all pending thoughts asynchronously.
        This is the key to non-blocking operation - it processes ALL thoughts,
        not just wakeup thoughts.
        """
        pending_thoughts = persistence.get_pending_thoughts_for_active_tasks()
        
        max_active = 10
        if hasattr(self.app_config, 'workflow') and self.app_config.workflow:
            max_active = getattr(self.app_config.workflow, 'max_active_thoughts', 10)
        
        limited_thoughts = pending_thoughts[:max_active]
        
        logger.info(f"Found {len(pending_thoughts)} PENDING thoughts, processing {len(limited_thoughts)} (max_active_thoughts: {max_active})")
        
        if not limited_thoughts:
            return 0
        
        processed_count = 0
        
        batch_size = 5
        
        for i in range(0, len(limited_thoughts), batch_size):
            batch = limited_thoughts[i:i + batch_size]
            
            tasks: List[Any] = []
            for thought in batch:
                persistence.update_thought_status(
                    thought_id=thought.thought_id,
                    status=ThoughtStatus.PROCESSING
                )
                
                task = self._process_single_thought(thought)
                tasks.append(task)
            
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
            processor = self.state_processors.get(self.state_manager.get_state())  # type: ignore[union-attr]
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
                updated_thought = await persistence.async_get_thought_by_id(thought.thought_id)
                if updated_thought and updated_thought.status in [ThoughtStatus.COMPLETED, ThoughtStatus.FAILED]:
                    logger.debug(f"Thought {thought.thought_id} was already handled with status {updated_thought.status.value}")
                    return True
                else:
                    logger.warning(f"No result from processing thought {thought.thought_id}")
                    return False
        except Exception as e:
            logger.error(f"Error processing thought {thought.thought_id}: {e}", exc_info=True)
            raise
    
    async def stop_processing(self) -> None:
        """Stop the processing loop gracefully."""
        if not self._processing_task or self._processing_task.done():
            logger.info("Processing loop is not running")
            return
        
        logger.info("Stopping processing loop...")
        if self._stop_event:
            self._stop_event.set()
        
        if self.state_manager.get_state() == AgentState.DREAM:
            await self.dream_processor.stop_dreaming()
        
        for processor in self.state_processors.values():
            try:
                await processor.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up {processor}: {e}")
        
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
    
    async def _processing_loop(self, num_rounds: Optional[int] = None) -> None:
        """Main processing loop with state management."""
        round_count = 0
        
        while not (self._stop_event and self._stop_event.is_set()):
            if num_rounds is not None and round_count >= num_rounds:
                logger.info(f"Reached target rounds ({num_rounds}), requesting graceful shutdown")
                request_global_shutdown(f"Processing completed after {num_rounds} rounds")
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
                        # Dream mode disabled - no automatic transition to DREAM state
                        pass
                    
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
            # Get delay from config, default to 1.0
            delay = 1.0
            if hasattr(self.app_config, 'workflow') and hasattr(self.app_config.workflow, 'round_delay_seconds'):
                delay = self.app_config.workflow.round_delay_seconds
            
            # State-specific delays override config
            if current_state == AgentState.WORK:
                delay = 3.0  # 3 second delay in work mode as requested
            elif current_state == AgentState.SOLITUDE:
                delay = 10.0  # Slower pace in solitude
            elif current_state == AgentState.DREAM:
                delay = 5.0  # Check dream state periodically
            
            if delay > 0 and not (self._stop_event and self._stop_event.is_set()):
                try:
                    if self._stop_event:
                        await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
                        break  # Stop event was set
                    else:
                        await asyncio.sleep(delay)
                except asyncio.TimeoutError:
                    pass  # Continue processing
        
        logger.info("Processing loop finished")
    
    async def _handle_state_transition(self, target_state: AgentState) -> None:
        """Handle transitioning to a new state."""
        current_state = self.state_manager.get_state()
        
        if not self.state_manager.transition_to(target_state):
            logger.error(f"Failed to transition from {current_state} to {target_state}")
            return
        
        if target_state == AgentState.DREAM:
            duration = 600
            await self.dream_processor.start_dreaming(duration)
            
        elif target_state == AgentState.WORK and current_state == AgentState.DREAM:
            await self.dream_processor.stop_dreaming()
            
            summary = self.dream_processor.get_dream_summary()
            logger.info(f"Dream summary: {summary}")
            
        if target_state in self.state_processors:
            processor = self.state_processors[target_state]
            await processor.initialize()
    
    async def process(self, round_number: int) -> Dict[str, Any]:
        """Execute one round of processing based on current state."""
        current_state = self.state_manager.get_state()
        processor = self.state_processors.get(current_state)
        
        if processor:
            return await processor.process(round_number)
        elif current_state == AgentState.DREAM:
            # Dream state handled separately
            return {"state": "dream", "round_number": round_number}
        else:
            return {"state": current_state.value, "round_number": round_number, "error": "No processor available"}

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
            status["wakeup_status"] = self.wakeup_processor.get_status()
            
        elif current_state == AgentState.WORK:
            status["work_status"] = self.work_processor.get_status()
            
        elif current_state == AgentState.PLAY:
            status["play_status"] = self.play_processor.get_status()
            
        elif current_state == AgentState.SOLITUDE:
            status["solitude_status"] = self.solitude_processor.get_status()
            
        elif current_state == AgentState.DREAM:
            status["dream_summary"] = self.dream_processor.get_dream_summary()
        
        # Add processor metrics
        status["processor_metrics"] = {}
        for state, processor in self.state_processors.items():
            status["processor_metrics"][state.value] = processor.get_metrics()
        
        return status
