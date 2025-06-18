"""
Main agent processor that coordinates all processing activities.
Uses v1 schemas and integrates state management.
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List, TYPE_CHECKING

from ciris_engine.schemas.config_schemas_v1 import AppConfig
from ciris_engine.schemas.identity_schemas_v1 import AgentIdentityRoot
from ciris_engine.schemas.states_v1 import AgentState
from ciris_engine import persistence
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, ThoughtStatus
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.utils.context_utils import build_dispatch_context

from ciris_engine.processor.thought_processor import ThoughtProcessor
from ciris_engine.protocols.processor_interface import ProcessorInterface
from ciris_engine.utils.shutdown_manager import is_global_shutdown_requested, get_global_shutdown_reason
if TYPE_CHECKING:
    from ciris_engine.action_handlers.action_dispatcher import ActionDispatcher

from .state_manager import StateManager
from .wakeup_processor import WakeupProcessor
from .work_processor import WorkProcessor
from .play_processor import PlayProcessor
from .dream_processor import DreamProcessor
from .solitude_processor import SolitudeProcessor
from .shutdown_processor import ShutdownProcessor

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
        agent_identity: AgentIdentityRoot,
        thought_processor: ThoughtProcessor,
        action_dispatcher: "ActionDispatcher",
        services: Dict[str, Any],
        startup_channel_id: str,
        runtime: Optional[Any] = None,
    ) -> None:
        """Initialize the agent processor with v1 configuration."""
        if not startup_channel_id:
            raise ValueError("startup_channel_id is required for agent processor")
        self.app_config = app_config
        self.agent_identity = agent_identity
        self.thought_processor = thought_processor
        self._action_dispatcher = action_dispatcher  # Store internally
        self.services = services
        self.startup_channel_id = startup_channel_id
        self.runtime = runtime  # Store runtime reference for preload tasks
        
        # Initialize state manager - agent always starts in SHUTDOWN state
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
        
        # Dream processor is initialized but will not be automatically entered via idle logic
        self.dream_processor = DreamProcessor(
            app_config=app_config,
            service_registry=services.get("service_registry"),
            cirisnode_url=app_config.cirisnode.base_url if hasattr(app_config, 'cirisnode') else "https://localhost:8001"
        )
        
        # Shutdown processor for graceful shutdown negotiation
        self.shutdown_processor = ShutdownProcessor(
            app_config=app_config,
            thought_processor=thought_processor,
            action_dispatcher=self._action_dispatcher,
            services=services,
            runtime=runtime
        )
        
        # Map states to processors
        self.state_processors = {
            AgentState.WAKEUP: self.wakeup_processor,
            AgentState.WORK: self.work_processor,
            AgentState.PLAY: self.play_processor,
            AgentState.SOLITUDE: self.solitude_processor,
            AgentState.SHUTDOWN: self.shutdown_processor,
            # DREAM is handled separately TODO: Integrate DREAM state with processor
        }
        
        # Processing control
        self.current_round_number = 0
        self._stop_event: Optional[asyncio.Event] = None
        self._processing_task: Optional[asyncio.Task] = None

        logger.info("AgentProcessor initialized with v1 schemas and modular processors")

    async def _load_preload_tasks(self) -> None:
        """Load preload tasks after successful WORK state transition."""
        try:
            if self.runtime and hasattr(self.runtime, "get_preload_tasks"):
                preload_tasks = self.runtime.get_preload_tasks()
                if preload_tasks:
                    logger.info(f"Loading {len(preload_tasks)} preload tasks after WORK state transition")
                    from ciris_engine.processor.task_manager import TaskManager
                    tm = TaskManager()
                    for desc in preload_tasks:
                        try:
                            tm.create_task(desc, context={"channel_id": self.startup_channel_id})
                            logger.info(f"Created preload task: {desc}")
                        except Exception as e:
                            logger.error(f"Error creating preload task '{desc}': {e}", exc_info=True)
                else:
                    logger.debug("No preload tasks to load")
            else:
                logger.debug("Runtime does not support preload tasks")
        except Exception as e:
            logger.error(f"Error loading preload tasks: {e}", exc_info=True)

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
        
        # Transition from SHUTDOWN to WAKEUP state when starting processing
        if self.state_manager.get_state() == AgentState.SHUTDOWN:
            if not self.state_manager.transition_to(AgentState.WAKEUP):
                logger.error("Failed to transition from SHUTDOWN to WAKEUP state")
                return
        elif self.state_manager.get_state() != AgentState.WAKEUP:
            logger.warning(f"Unexpected state {self.state_manager.get_state()} when starting processing")
            if not self.state_manager.transition_to(AgentState.WAKEUP):
                logger.error(f"Failed to transition from {self.state_manager.get_state()} to WAKEUP state")
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
                
                # Use shorter delay for mock LLM
                llm_service = self.services.get('llm_service')
                is_mock_llm = llm_service and type(llm_service).__name__ == 'MockLLMService'
                round_delay = 0.1 if is_mock_llm else 5.0
                await asyncio.sleep(round_delay)
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

        await self._load_preload_tasks()

        if hasattr(self, "runtime") and self.runtime is not None and hasattr(self.runtime, "start_interactive_console"):
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
        Process all pending thoughts asynchronously with comprehensive error handling.
        This is the key to non-blocking operation - it processes ALL thoughts,
        not just wakeup thoughts.
        """
        try:
            # Get current state to filter thoughts appropriately
            current_state = self.state_manager.get_state()
            
            pending_thoughts = persistence.get_pending_thoughts_for_active_tasks()
            
            # If in SHUTDOWN state, only process thoughts for shutdown tasks
            if current_state == AgentState.SHUTDOWN:
                shutdown_thoughts = [t for t in pending_thoughts if t.source_task_id and t.source_task_id.startswith('shutdown_')]
                pending_thoughts = shutdown_thoughts
                logger.info(f"In SHUTDOWN state - filtering to {len(shutdown_thoughts)} shutdown-related thoughts only")
            
            max_active = 10
            if hasattr(self.app_config, 'workflow') and self.app_config.workflow:
                max_active = getattr(self.app_config.workflow, 'max_active_thoughts', 10)
            
            limited_thoughts = pending_thoughts[:max_active]
            
            logger.info(f"Found {len(pending_thoughts)} PENDING thoughts, processing {len(limited_thoughts)} (max_active_thoughts: {max_active})")
            
            if not limited_thoughts:
                return 0
            
            processed_count = 0
            failed_count = 0
            
            batch_size = 5
            
            for i in range(0, len(limited_thoughts), batch_size):
                try:
                    batch = limited_thoughts[i:i + batch_size]
                    
                    tasks: List[Any] = []
                    for thought in batch:
                        try:
                            persistence.update_thought_status(
                                thought_id=thought.thought_id,
                                status=ThoughtStatus.PROCESSING
                            )
                            
                            task = self._process_single_thought(thought)
                            tasks.append(task)
                        except Exception as e:
                            logger.error(f"Error preparing thought {thought.thought_id} for processing: {e}", exc_info=True)
                            failed_count += 1
                            continue
                    
                    if not tasks:
                        continue
                    
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    for result, thought in zip(results, batch):
                        try:
                            if isinstance(result, Exception):
                                logger.error(f"Error processing thought {thought.thought_id}: {result}")
                                persistence.update_thought_status(
                                    thought_id=thought.thought_id,
                                    status=ThoughtStatus.FAILED,
                                    final_action={"error": str(result)}
                                )
                                failed_count += 1
                            else:
                                processed_count += 1
                        except Exception as e:
                            logger.error(f"Error handling result for thought {thought.thought_id}: {e}", exc_info=True)
                            failed_count += 1
                            
                except Exception as e:
                    logger.error(f"Error processing thought batch {i//batch_size + 1}: {e}", exc_info=True)
                    failed_count += len(batch) if 'batch' in locals() else batch_size
            
            if failed_count > 0:
                logger.warning(f"Thought processing completed with {failed_count} failures out of {len(limited_thoughts)} attempts")
            
            return processed_count
            
        except Exception as e:
            logger.error(f"CRITICAL: Error in _process_pending_thoughts_async: {e}", exc_info=True)
            return 0


    async def _process_single_thought(self, thought: Thought) -> bool:
        """Process a single thought and dispatch its action, with comprehensive error handling."""
        try:
            # Create processing queue item
            item = ProcessingQueueItem.from_thought(thought)

            # Use the current state's processor for fallback-aware processing
            processor = self.state_processors.get(self.state_manager.get_state())
            if processor is None:
                logger.error(f"No processor found for state {self.state_manager.get_state()}")
                persistence.update_thought_status(
                    thought_id=thought.thought_id,
                    status=ThoughtStatus.FAILED,
                    final_action={"error": f"No processor for state {self.state_manager.get_state()}"}
                )
                return False

            # Use fallback-aware process_thought_item
            try:
                result = await processor.process_thought_item(item, context={"origin": "wakeup_async"})
            except Exception as e:
                logger.error(f"Error in processor.process_thought_item for thought {thought.thought_id}: {e}", exc_info=True)
                persistence.update_thought_status(
                    thought_id=thought.thought_id,
                    status=ThoughtStatus.FAILED,
                    final_action={"error": f"Processor error: {e}"}
                )
                return False

            if result:
                try:
                    # Get the task for context
                    task = persistence.get_task_by_id(thought.source_task_id)
                    
                    # Extract guardrail result if available
                    guardrail_result = getattr(result, '_guardrail_result', None)
                    
                    dispatch_context = build_dispatch_context(
                        thought=thought, 
                        task=task, 
                        app_config=self.app_config, 
                        round_number=self.current_round_number,
                        guardrail_result=guardrail_result,
                        action_type=result.selected_action if result else None
                    )
                    # Services should be accessed via service registry, not passed in context
                    # to avoid serialization issues during audit logging
                    
                    await self.action_dispatcher.dispatch(
                        action_selection_result=result,
                        thought=thought,
                        dispatch_context=dispatch_context
                    )
                    return True
                except Exception as e:
                    logger.error(f"Error in action_dispatcher.dispatch for thought {thought.thought_id}: {e}", exc_info=True)
                    persistence.update_thought_status(
                        thought_id=thought.thought_id,
                        status=ThoughtStatus.FAILED,
                        final_action={"error": f"Dispatch error: {e}"}
                    )
                    return False
            else:
                try:
                    # Check if the thought was already handled (e.g., TASK_COMPLETE)
                    updated_thought = await persistence.async_get_thought_by_id(thought.thought_id)
                    if updated_thought and updated_thought.status in [ThoughtStatus.COMPLETED, ThoughtStatus.FAILED]:
                        logger.debug(f"Thought {thought.thought_id} was already handled with status {updated_thought.status.value}")
                        return True
                    else:
                        logger.warning(f"No result from processing thought {thought.thought_id}")
                        persistence.update_thought_status(
                            thought_id=thought.thought_id,
                            status=ThoughtStatus.FAILED,
                            final_action={"error": "No processing result and thought not already handled"}
                        )
                        return False
                except Exception as e:
                    logger.error(f"Error checking thought status for {thought.thought_id}: {e}", exc_info=True)
                    return False
        except Exception as e:
            logger.error(f"CRITICAL: Unhandled error processing thought {thought.thought_id}: {e}", exc_info=True)
            try:
                persistence.update_thought_status(
                    thought_id=thought.thought_id,
                    status=ThoughtStatus.FAILED,
                    final_action={"error": f"Critical processing error: {e}"}
                )
            except Exception as update_error:
                logger.error(f"Failed to update thought status after critical error: {update_error}", exc_info=True)
            raise
    
    async def stop_processing(self) -> None:
        """Stop the processing loop gracefully."""
        if not self._processing_task or self._processing_task.done():
            logger.info("Processing loop is not running")
            return
        
        logger.info("Stopping processing loop...")
        if self._stop_event:
            self._stop_event.set()
        
        if self.state_manager.get_state() == AgentState.DREAM and self.dream_processor:
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
        """Main processing loop with state management and comprehensive exception handling."""
        round_count = 0
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        try:
            while not (self._stop_event and self._stop_event.is_set()):
                try:
                    if num_rounds is not None and round_count >= num_rounds:
                        logger.info(f"Reached target rounds ({num_rounds}), requesting graceful shutdown")
                        request_global_shutdown(f"Processing completed after {num_rounds} rounds")
                        break
                    
                    # Update round number
                    # self.thought_processor.advance_round()  # Removed nonexistent method
                    self.current_round_number += 1
                    
                    # Get current state
                    current_state = self.state_manager.get_state()
                    
                    # Never transition away from SHUTDOWN state
                    if current_state == AgentState.SHUTDOWN:
                        logger.debug("In SHUTDOWN state, skipping transition checks")
                    else:
                        # Check if shutdown has been requested
                        if is_global_shutdown_requested():
                            shutdown_reason = get_global_shutdown_reason() or "Unknown reason"
                            logger.info(f"Global shutdown requested: {shutdown_reason}")
                            # Transition to shutdown state if not already there
                            if self.state_manager.can_transition_to(AgentState.SHUTDOWN):
                                await self._handle_state_transition(AgentState.SHUTDOWN)
                            else:
                                logger.error(f"Cannot transition from {current_state} to SHUTDOWN")
                                break
                        else:
                            # Check for automatic state transitions only if not shutting down
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
                            consecutive_errors = 0  # Reset error counter on success
                            
                            # Check for state transition recommendations
                            if current_state == AgentState.WORK:
                                # Dream processor exists but no automatic idle-based transition to DREAM state
                                pass
                            
                            elif current_state == AgentState.SOLITUDE and processor == self.solitude_processor:
                                if result.get("should_exit_solitude"):
                                    logger.info(f"Exiting solitude: {result.get('exit_reason', 'Unknown reason')}")
                                    await self._handle_state_transition(AgentState.WORK)
                                    
                        except Exception as e:
                            consecutive_errors += 1
                            logger.error(f"Error in {processor} for state {current_state}: {e}", exc_info=True)
                            
                            if consecutive_errors >= max_consecutive_errors:
                                logger.error(f"Too many consecutive processing errors ({consecutive_errors}), requesting shutdown")
                                request_global_shutdown(f"Processing errors: {consecutive_errors} consecutive failures")
                                break
                            
                            # Add backoff delay after errors
                            await asyncio.sleep(min(consecutive_errors * 2, 30))
                            
                    elif current_state == AgentState.DREAM:
                        # Dream processing is handled by dream_processor
                        await asyncio.sleep(5)  # Check periodically
                        
                    elif current_state == AgentState.SHUTDOWN:
                        # Process shutdown state with negotiation
                        logger.info("In SHUTDOWN state, processing shutdown negotiation")
                        processor = self.state_processors.get(current_state)
                        if processor:
                            try:
                                result = await processor.process(self.current_round_number)
                                round_count += 1
                                consecutive_errors = 0
                                
                                # Check if shutdown is complete
                                if processor == self.shutdown_processor and self.shutdown_processor.shutdown_complete:
                                    logger.info("Shutdown negotiation complete, exiting processing loop")
                                    break
                            except Exception as e:
                                consecutive_errors += 1
                                logger.error(f"Error in shutdown processor: {e}", exc_info=True)
                                break
                        else:
                            logger.error("No shutdown processor available")
                            break
                        
                    else:
                        logger.warning(f"No processor for state: {current_state}")
                        await asyncio.sleep(1)
                    
                    # Brief delay between rounds
                    # Get delay from config, using mock LLM delay if enabled
                    delay = 1.0
                    if hasattr(self.app_config, 'workflow'):
                        mock_llm = getattr(self.app_config, 'mock_llm', False)
                        if hasattr(self.app_config.workflow, 'get_round_delay'):
                            delay = self.app_config.workflow.get_round_delay(mock_llm)
                        elif hasattr(self.app_config.workflow, 'round_delay_seconds'):
                            delay = self.app_config.workflow.round_delay_seconds
                    
                    # State-specific delays override config only if not using mock LLM
                    if not getattr(self.app_config, 'mock_llm', False):
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
                            
                except Exception as e:
                    consecutive_errors += 1
                    logger.error(f"CRITICAL: Unhandled error in processing loop round {self.current_round_number}: {e}", exc_info=True)
                    
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"Processing loop has failed {consecutive_errors} consecutive times, requesting shutdown")
                        request_global_shutdown(f"Critical processing loop failure: {consecutive_errors} consecutive errors")
                        break
                    
                    # Emergency backoff after critical errors
                    await asyncio.sleep(min(consecutive_errors * 5, 60))
                    
        except Exception as e:
            logger.error(f"FATAL: Catastrophic error in processing loop: {e}", exc_info=True)
            request_global_shutdown(f"Catastrophic processing loop error: {e}")
            raise
        finally:
            logger.info("Processing loop finished")
    
    async def _handle_state_transition(self, target_state: AgentState) -> None:
        """Handle transitioning to a new state."""
        current_state = self.state_manager.get_state()
        
        if not self.state_manager.transition_to(target_state):
            logger.error(f"Failed to transition from {current_state} to {target_state}")
            return
        
        if target_state == AgentState.SHUTDOWN:
            # Special handling for shutdown transition
            logger.info("Transitioning to SHUTDOWN - clearing non-shutdown thoughts from queue")
            # The shutdown processor will create its own thoughts
            # Any pending thoughts will be cleaned up on next startup
            
        elif target_state == AgentState.DREAM:
            logger.info("DREAM state transition requested - dream processor is available but not automatically triggered")
            
        elif target_state == AgentState.WORK and current_state == AgentState.DREAM:
            if self.dream_processor:
                await self.dream_processor.stop_dreaming()
                summary = self.dream_processor.get_dream_summary()
                logger.info(f"Dream summary: {summary}")
            else:
                logger.info("Dream processor not available, no cleanup needed")
            
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
        status: Dict[str, Any] = {
            "state": self.state_manager.get_state().value,
            "state_duration": self.state_manager.get_state_duration(),
            "round_number": self.current_round_number,
            "is_processing": self._processing_task is not None and not self._processing_task.done(),
        }
        
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
            if self.dream_processor:
                status["dream_summary"] = self.dream_processor.get_dream_summary()
            else:
                status["dream_summary"] = {"state": "unavailable", "error": "Dream processor not available"}
        
        status["processor_metrics"] = {}
        for state, processor in self.state_processors.items():
            status["processor_metrics"][state.value] = processor.get_metrics()
        
        status["queue_status"] = self._get_detailed_queue_status()
        
        return status
    
    def _get_detailed_queue_status(self) -> Dict[str, Any]:
        """Get detailed processing queue status information."""
        try:
            # Get thought counts by status
            from ciris_engine import persistence
            from ciris_engine.schemas.agent_core_schemas_v1 import ThoughtStatus
            
            pending_count = persistence.count_thoughts_by_status(ThoughtStatus.PENDING)
            processing_count = persistence.count_thoughts_by_status(ThoughtStatus.PROCESSING)
            completed_count = persistence.count_thoughts_by_status(ThoughtStatus.COMPLETED)
            failed_count = persistence.count_thoughts_by_status(ThoughtStatus.FAILED)
            
            # Get recent thought activity
            recent_thoughts = []
            try:
                # Get last 5 thoughts for activity overview
                from ciris_engine.persistence.models.thoughts import get_recent_thoughts
                recent_data = get_recent_thoughts(limit=5)
                for thought_data in recent_data:
                    content_str = str(thought_data.content or "")
                    recent_thoughts.append({
                        "thought_id": thought_data.thought_id,
                        "thought_type": thought_data.thought_type or "unknown",
                        "status": thought_data.status or "unknown",
                        "created_at": getattr(thought_data, "created_at", "unknown"),
                        "content_preview": content_str[:100] + "..." if len(content_str) > 100 else content_str
                    })
            except Exception as e:
                logger.warning(f"Could not fetch recent thoughts: {e}")
                recent_thoughts = []
            
            # Get task information
            task_info: Dict[str, Any] = {}
            try:
                if hasattr(self, 'work_processor') and self.work_processor:
                    task_info = {
                        "active_tasks": self.work_processor.task_manager.get_active_task_count(),
                        "pending_tasks": self.work_processor.task_manager.get_pending_task_count(),
                    }
            except Exception as e:
                logger.warning(f"Could not fetch task info: {e}")
                task_info = {"error": str(e)}
            
            return {
                "thought_counts": {
                    "pending": pending_count,
                    "processing": processing_count,
                    "completed": completed_count,
                    "failed": failed_count,
                    "total": pending_count + processing_count + completed_count + failed_count
                },
                "recent_activity": recent_thoughts,
                "task_summary": task_info,
                "queue_health": {
                    "has_pending_work": pending_count > 0,
                    "has_processing_work": processing_count > 0,
                    "has_recent_failures": failed_count > 0,
                    "queue_utilization": "high" if pending_count + processing_count > 10 else "medium" if pending_count + processing_count > 3 else "low"
                }
            }
        except Exception as e:
            logger.error(f"Error getting detailed queue status: {e}", exc_info=True)
            return {
                "error": str(e),
                "thought_counts": {"error": "Could not fetch counts"},
                "recent_activity": [],
                "task_summary": {"error": "Could not fetch task info"},
                "queue_health": {"error": "Could not determine health"}
            }
