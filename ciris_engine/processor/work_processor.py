"""
Work processor handling normal task and thought processing.
Enhanced with proper context building and service passing.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from ciris_engine.schemas.states import AgentState
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, TaskStatus
from ciris_engine import persistence
from ciris_engine.processor.base_processor import BaseProcessor
from ciris_engine.processor.task_manager import TaskManager
from ciris_engine.processor.thought_manager import ThoughtManager
from ciris_engine.processor.thought_processor import ThoughtProcessor
from ciris_engine.utils.context_utils import build_dispatch_context

logger = logging.getLogger(__name__)


class WorkProcessor(BaseProcessor):
    """Handles the WORK state for normal task/thought processing."""

    def __init__(self, *args, startup_channel_id: Optional[str] = None, **kwargs):
        """Initialize work processor."""
        self.startup_channel_id = startup_channel_id
        super().__init__(*args, **kwargs)
        
        # Extract config values with defaults
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
                # Handle idle state
                round_metrics["was_idle"] = True
                self.idle_rounds += 1
                await self._handle_idle_state(round_number)
            
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
        
        # Mark thoughts as PROCESSING
        batch = self.thought_manager.mark_thoughts_processing(batch, round_number)
        if not batch:
            logger.warning("No thoughts could be marked as PROCESSING")
            return 0
        
        processed_count = 0
        
        # Process each thought
        for item in batch:
            try:
                result = await self._process_single_thought(item)
                processed_count += 1
                
                if result is None:
                    # Thought was re-queued (e.g., PONDER)
                    logger.debug(f"Thought {item.thought_id} was re-queued")
                else:
                    # Dispatch the action
                    await self._dispatch_thought_result(item, result)
                    
            except Exception as e:
                logger.error(f"Error processing thought {item.thought_id}: {e}", exc_info=True)
                self._mark_thought_failed(item.thought_id, str(e))
        
        return processed_count
    
    async def _process_single_thought(self, item: Any) -> Any:
        """Process a single thought item."""
        return await self.process_thought_item(item)
    
    async def _dispatch_thought_result(self, item: Any, result: Any):
        """Dispatch the result of thought processing."""
        thought_id = item.thought_id
        
        logger.info(
            f"Dispatching action {result.selected_action} "
            f"for thought {thought_id}"
        )
        
        # Get full thought object
        thought_obj = persistence.get_thought_by_id(thought_id)
        if not thought_obj:
            logger.error(f"Could not retrieve thought {thought_id} for dispatch")
            return

        # Get the task object for context
        task = persistence.get_task_by_id(item.source_task_id)
        dispatch_context = build_dispatch_context(
            thought=thought_obj, 
            task=task, 
            app_config=self.app_config, 
            startup_channel_id=getattr(self, 'startup_channel_id', None), 
            round_number=getattr(item, 'round_number', 0),
            extra_context=getattr(item, 'initial_context', {})
        )
        
        # Add services from processor for convenience
        if hasattr(self, 'services') and self.services:
            dispatch_context.update({"services": self.services})
            
            # Add specific service references for convenience
            if "discord_service" in self.services:
                dispatch_context["discord_service"] = self.services["discord_service"]
        
        # Add discord_service directly if available
        if hasattr(self, 'discord_service'):
            dispatch_context["discord_service"] = self.discord_service
        
        try:
            await self.dispatch_action(result, thought_obj, dispatch_context)
        except Exception as e:
            logger.error(f"Error dispatching action for thought {thought_id}: {e}")
            self._mark_thought_failed(
                thought_id, 
                f"Dispatch failed: {str(e)}"
            )
    
    async def _handle_idle_state(self, round_number: int):
        """Handle idle state when no thoughts are pending."""
        logger.info(f"Round {round_number}: No thoughts to process (idle rounds: {self.idle_rounds})")
        
        # Create job thought if needed
        created_job = self.thought_manager.handle_idle_state(round_number)
        
        if created_job:
            logger.info("Created job thought for idle monitoring")
        else:
            logger.debug("No job thought needed")
    
    def _mark_thought_failed(self, thought_id: str, error: str):
        """Mark a thought as failed."""
        persistence.update_thought_status(
            thought_id=thought_id,
            status=ThoughtStatus.FAILED,
            final_action={"error": error}
        )
    
    def get_idle_duration(self) -> float:
        """Get duration in seconds since last activity."""
        return (datetime.now(timezone.utc) - self.last_activity_time).total_seconds()
    
    def get_work_stats(self) -> Dict[str, Any]:
        """Get current work processing statistics."""
        return {
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
    
    def should_transition_to_dream(self, idle_threshold: float = 300) -> bool:
        """
        Check if we should recommend transitioning to DREAM state.
        
        Args:
            idle_threshold: Seconds of idle time before recommending DREAM
        
        Returns:
            True if DREAM state is recommended
        """
        # Check idle duration
        if self.get_idle_duration() < idle_threshold:
            return False
        
        # Check if there's truly nothing to do
        if (self.task_manager.get_active_task_count() == 0 and
            self.task_manager.get_pending_task_count() == 0 and
            self.thought_manager.get_pending_thought_count() == 0):
            return True
        
        # If we've been idle for many rounds despite having work
        if self.idle_rounds > 10:
            logger.warning(
                f"Been idle for {self.idle_rounds} rounds despite having work. "
                "Consider checking for stuck tasks/thoughts."
            )
        
        return False