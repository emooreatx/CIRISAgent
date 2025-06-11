"""
Work processor handling normal task and thought processing.
Enhanced with proper context building and service passing.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from ciris_engine.schemas.states_v1 import AgentState
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, TaskStatus
from ciris_engine import persistence
from ciris_engine.processor.base_processor import BaseProcessor
from ciris_engine.processor.task_manager import TaskManager
from ciris_engine.processor.thought_manager import ThoughtManager
from ciris_engine.processor.thought_processor import ThoughtProcessor
from ciris_engine.protocols.processor_interface import ProcessorInterface
from ciris_engine.utils.context_utils import build_dispatch_context

logger = logging.getLogger(__name__)


class WorkProcessor(BaseProcessor, ProcessorInterface):
    """Handles the WORK state for normal task/thought processing."""

    def __init__(
        self,
        app_config,
        thought_processor,
        action_dispatcher,
        services: Dict[str, Any],
        startup_channel_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Initialize work processor."""
        self.startup_channel_id = startup_channel_id
        super().__init__(app_config, thought_processor, action_dispatcher, services, **kwargs)
        
        workflow_config = getattr(self.app_config, 'workflow', None)
        if workflow_config:
            max_active_tasks = getattr(workflow_config, 'max_active_tasks', 10)
            max_active_thoughts = getattr(workflow_config, 'max_active_thoughts', 50)
        else:
            max_active_tasks = 10
            max_active_thoughts = 50
        
        self.task_manager = TaskManager(max_active_tasks=max_active_tasks)
        self.thought_manager = ThoughtManager(
            max_active_thoughts=max_active_thoughts,
            default_channel_id=self.startup_channel_id,
        )
        self.last_activity_time = datetime.now(timezone.utc)
        self.idle_rounds = 0
    
    def get_supported_states(self) -> List[AgentState]:
        """Work processor handles WORK and PLAY states."""
        return [AgentState.WORK, AgentState.PLAY]
    
    async def can_process(self, state: AgentState) -> bool:
        """Check if we can process the given state."""
        return state in self.get_supported_states()
    
    async def process(self, round_number: int) -> Dict[str, Any]:
        """Execute one round of work processing."""
        start_time = datetime.now(timezone.utc)
        logger.info(f"--- Starting Work Round {round_number} ---")
        
        round_metrics = {
            "round_number": round_number,
            "tasks_activated": 0,
            "thoughts_generated": 0,
            "thoughts_processed": 0,
            "errors": 0,
            "was_idle": False
        }
        
        try:
            # Phase 1: Task activation
            activated = self.task_manager.activate_pending_tasks()
            round_metrics["tasks_activated"] = activated
            
            # Phase 2: Seed thought generation
            tasks_needing_seed = self.task_manager.get_tasks_needing_seed()
            generated = self.thought_manager.generate_seed_thoughts(
                tasks_needing_seed, 
                round_number
            )
            round_metrics["thoughts_generated"] = generated
            
            # Phase 3: Populate processing queue
            queue_size = self.thought_manager.populate_queue(round_number)
            
            if queue_size > 0:
                # Phase 4: Process thought batch
                batch = self.thought_manager.get_queue_batch()
                processed = await self._process_batch(batch, round_number)
                round_metrics["thoughts_processed"] = processed
                
                # Update activity tracking
                self.last_activity_time = start_time
                self.idle_rounds = 0
                round_metrics["was_idle"] = False
            else:
                # Handle idle state - DISABLED
                round_metrics["was_idle"] = True
                # Idle mode disabled - no automatic transitions
                # self.idle_rounds += 1
                # await self._handle_idle_state(round_number)
                logger.debug(f"Round {round_number}: No thoughts to process (idle mode disabled)")
            
            # Update metrics
            self.metrics["rounds_completed"] += 1
            
        except Exception as e:
            logger.error(f"Error in work round {round_number}: {e}", exc_info=True)
            round_metrics["errors"] += 1
            self.metrics["errors"] += 1
        
        # Calculate round duration
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        round_metrics["duration_seconds"] = duration
        
        logger.info(
            f"--- Finished Work Round {round_number} "
            f"(Duration: {duration:.2f}s, Processed: {round_metrics['thoughts_processed']}) ---"
        )
        
        return round_metrics
    
    async def _process_batch(self, batch: List[Any], round_number: int) -> int:
        """Process a batch of thoughts."""
        if not batch:
            return 0
        
        logger.info(f"Processing batch of {len(batch)} thoughts")
        
        batch = self.thought_manager.mark_thoughts_processing(batch, round_number)
        if not batch:
            logger.warning("No thoughts could be marked as PROCESSING")
            return 0
        
        processed_count = 0
        
        for item in batch:
            try:
                result = await self._process_single_thought(item)
                processed_count += 1
                
                if result is None:
                    logger.debug(f"Thought {item.thought_id} was re-queued")
                else:
                    await self._dispatch_thought_result(item, result)
                    
            except Exception as e:
                logger.error(f"Error processing thought {item.thought_id}: {e}", exc_info=True)
                self._mark_thought_failed(item.thought_id, str(e))
        
        return processed_count
    
    async def _process_single_thought(self, item: Any) -> Any:
        """Process a single thought item."""
        return await self.process_thought_item(item)
    
    async def _dispatch_thought_result(self, item: Any, result: Any) -> None:
        """Dispatch the result of thought processing."""
        thought_id = item.thought_id
        
        logger.info(
            f"Dispatching action {result.selected_action} "
            f"for thought {thought_id}"
        )
        
        thought_obj = await persistence.async_get_thought_by_id(thought_id)
        if not thought_obj:
            logger.error(f"Could not retrieve thought {thought_id} for dispatch")
            return

        task = persistence.get_task_by_id(item.source_task_id)
        dispatch_context = build_dispatch_context(
            thought=thought_obj, 
            task=task, 
            app_config=self.app_config, 
            round_number=getattr(item, 'round_number', 0),
            extra_context=getattr(item, 'initial_context', {})
        )
        
        # Services should be accessed via service registry, not passed in context
        # to avoid serialization issues during audit logging
        
        try:
            await self.dispatch_action(result, thought_obj, dispatch_context)
        except Exception as e:
            logger.error(f"Error dispatching action for thought {thought_id}: {e}")
            self._mark_thought_failed(
                thought_id, 
                f"Dispatch failed: {str(e)}"
            )
    
    async def _handle_idle_state(self, round_number: int) -> None:
        """Handle idle state when no thoughts are pending."""
        logger.info(f"Round {round_number}: No thoughts to process (idle rounds: {self.idle_rounds})")
        
        # Create job thought if needed
        created_job = self.thought_manager.handle_idle_state(round_number)
        
        if created_job:
            logger.info("Created job thought for idle monitoring")
        else:
            logger.debug("No job thought needed")
    
    def _mark_thought_failed(self, thought_id: str, error: str) -> None:
        """Mark a thought as failed."""
        persistence.update_thought_status(
            thought_id=thought_id,
            status=ThoughtStatus.FAILED,
            final_action={"error": error}
        )
    
    def get_idle_duration(self) -> float:
        """Get duration in seconds since last activity."""
        return (datetime.now(timezone.utc) - self.last_activity_time).total_seconds()
    
    
    def should_transition_to_dream(self, idle_threshold: float = 300) -> bool:
        """
        Check if we should recommend transitioning to DREAM state.
        
        DISABLED: Idle mode transitions are disabled.
        
        Args:
            idle_threshold: Seconds of idle time before recommending DREAM
        
        Returns:
            Always returns False (idle mode disabled)
        """
        # Idle mode disabled - no automatic transitions
        return False

    # ProcessorInterface implementation
    async def start_processing(self, num_rounds: Optional[int] = None) -> None:
        """Start the work processing loop."""
        import asyncio
        round_num = 0
        self._running = True
        
        while self._running and (num_rounds is None or round_num < num_rounds):
            await self.process(round_num)
            round_num += 1
            
            # Check if we should transition to dream state
            if self.should_transition_to_dream():
                logger.info("Work processor recommends transitioning to DREAM state due to inactivity")
                break
                
            await asyncio.sleep(1)  # Brief pause between rounds

    async def stop_processing(self) -> None:
        """Stop work processing and clean up resources."""
        self._running = False
        logger.info("Work processor stopped")

    def get_status(self) -> Dict[str, Any]:
        """Get current work processor status and metrics."""
        work_stats = {
            "last_activity": self.last_activity_time.isoformat(),
            "idle_duration_seconds": self.get_idle_duration(),
            "idle_rounds": self.idle_rounds,
            "active_tasks": self.task_manager.get_active_task_count(),
            "pending_tasks": self.task_manager.get_pending_task_count(),
            "pending_thoughts": self.thought_manager.get_pending_thought_count(),
            "processing_thoughts": self.thought_manager.get_processing_thought_count(),
            "total_rounds": self.metrics.get("rounds_completed", 0),
            "total_processed": self.metrics.get("items_processed", 0),
            "total_errors": self.metrics.get("errors", 0)
        }
        return {
            "processor_type": "work",
            "supported_states": [state.value for state in self.get_supported_states()],
            "is_running": getattr(self, '_running', False),
            "work_stats": work_stats,
            "metrics": getattr(self, 'metrics', {}),
            "startup_channel_id": self.startup_channel_id,
            "should_transition_to_dream": self.should_transition_to_dream()
        }