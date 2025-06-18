"""
Shutdown processor for graceful agent shutdown.

This processor implements the SHUTDOWN state handling by creating
a standard task that the agent processes through normal cognitive flow.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, TYPE_CHECKING

from ciris_engine.processor.base_processor import BaseProcessor
from ciris_engine.schemas.states_v1 import AgentState
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtType, ThoughtStatus
from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought
from ciris_engine.schemas.context_schemas_v1 import ThoughtContext, SystemSnapshot
from ciris_engine.schemas.identity_schemas_v1 import ShutdownContext
from ciris_engine import persistence
from ciris_engine.utils.shutdown_manager import get_shutdown_manager
from ciris_engine.utils.channel_utils import create_channel_context
from ciris_engine.schemas.config_schemas_v1 import AppConfig
from ciris_engine.processor.thought_processor import ThoughtProcessor
from ciris_engine.processor.thought_manager import ThoughtManager

if TYPE_CHECKING:
    from ciris_engine.action_handlers.action_dispatcher import ActionDispatcher

logger = logging.getLogger(__name__)


class ShutdownProcessor(BaseProcessor):
    """
    Handles the SHUTDOWN state by creating a standard task 
    that the agent processes through normal cognitive flow.
    """
    
    def __init__(
        self,
        app_config: AppConfig,
        thought_processor: ThoughtProcessor,
        action_dispatcher: "ActionDispatcher",
        services: Dict[str, Any],
        runtime: Optional[Any] = None,
    ) -> None:
        super().__init__(app_config, thought_processor, action_dispatcher, services)
        self.runtime = runtime
        self.shutdown_task: Optional[Task] = None
        self.shutdown_complete = False
        self.shutdown_result: Optional[Dict[str, Any]] = None
        
        # Initialize thought manager for seed thought generation
        workflow_config = getattr(self.app_config, 'workflow', None)
        max_active_thoughts = getattr(workflow_config, 'max_active_thoughts', 50) if workflow_config else 50
        self.thought_manager = ThoughtManager(max_active_thoughts=max_active_thoughts)
        
    def get_supported_states(self) -> List[AgentState]:
        """We only handle SHUTDOWN state."""
        return [AgentState.SHUTDOWN]
        
    async def can_process(self, state: AgentState) -> bool:
        """We can always process shutdown state."""
        return state == AgentState.SHUTDOWN
        
    async def process(self, round_number: int) -> Dict[str, Any]:
        """
        Execute shutdown processing for one round.
        Creates a task on first round, monitors for completion.
        When called directly (not in main loop), also processes thoughts.
        """
        logger.info(f"=== SHUTDOWN PROCESSOR: Round {round_number} ===")
        
        try:
            # Create shutdown task if not exists
            if not self.shutdown_task:
                self._create_shutdown_task()
            
            # Check if task is complete
            current_task = persistence.get_task_by_id(self.shutdown_task.task_id)
            if not current_task:
                logger.error("Shutdown task disappeared!")
                return {
                    "status": "error",
                    "message": "Shutdown task not found"
                }
            
            # If task is pending, activate it
            if current_task.status == TaskStatus.PENDING:
                persistence.update_task_status(self.shutdown_task.task_id, TaskStatus.ACTIVE)
                logger.info("Activated shutdown task")
            
            # Generate seed thought if needed
            if current_task.status == TaskStatus.ACTIVE:
                existing_thoughts = persistence.get_thoughts_by_task_id(self.shutdown_task.task_id)
                if not existing_thoughts:
                    # Use thought manager to generate seed thought
                    generated = self.thought_manager.generate_seed_thoughts([current_task], round_number)
                    logger.info(f"Generated {generated} seed thoughts for shutdown task")
            
            # Process pending thoughts if we're being called directly (not in main loop)
            # This allows shutdown negotiation to happen when runtime calls us manually
            await self._process_shutdown_thoughts()
            
            # Re-fetch task to check updated status
            current_task = persistence.get_task_by_id(self.shutdown_task.task_id)
            
            # Check task completion status
            if current_task.status == TaskStatus.COMPLETED:
                self.shutdown_complete = True
                self.shutdown_result = {
                    "status": "completed",
                    "action": "shutdown_accepted",
                    "message": "Agent acknowledged shutdown"
                }
                logger.info("✓ Shutdown task completed - agent accepted shutdown")
                return self.shutdown_result
            elif current_task.status == TaskStatus.FAILED:
                # Task failed - could be REJECT or error
                self.shutdown_complete = True
                self.shutdown_result = await self._check_failure_reason(current_task)
                return self.shutdown_result
            
            # Still processing
            thoughts = persistence.get_thoughts_by_task_id(self.shutdown_task.task_id)
            thought_statuses = [(t.thought_id, t.status.value) for t in thoughts] if thoughts else []
            
            return {
                "status": "in_progress",
                "task_status": current_task.status.value,
                "thoughts": thought_statuses,
                "message": "Waiting for agent response"
            }
            
        except Exception as e:
            logger.error(f"Error in shutdown processor: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }
            
    def _create_shutdown_task(self) -> None:
        """Create the shutdown task."""
        shutdown_manager = get_shutdown_manager()
        reason = shutdown_manager.get_shutdown_reason() or "Graceful shutdown requested"
        
        now_iso = datetime.now(timezone.utc).isoformat()
        
        # Create task context with shutdown details and proper channel context
        # Get channel ID from runtime if available
        channel_id = None
        if self.runtime and hasattr(self.runtime, 'startup_channel_id'):
            channel_id = self.runtime.startup_channel_id
        elif self.runtime and hasattr(self.runtime, 'get_primary_channel_id'):
            channel_id = self.runtime.get_primary_channel_id()
        
        # If no channel ID available, use a system channel
        if not channel_id:
            channel_id = "system"
            logger.warning("No channel ID available for shutdown task, using 'system'")
        
        # Create proper context with channel information
        context = ThoughtContext(
            system_snapshot=SystemSnapshot(
                channel_context=create_channel_context(channel_id)
            )
        )
        context.identity_context = f"System shutdown requested: {reason}"
        
        # Store shutdown context in runtime for system snapshot
        if self.runtime:
            self.runtime.current_shutdown_context = ShutdownContext(
                is_terminal=False,
                reason=reason,
                initiated_by="runtime",
                allow_deferral=True,
                expected_reactivation=None,
                agreement_context=None
            )
        
        self.shutdown_task = Task(
            task_id=f"shutdown_{uuid.uuid4().hex[:8]}",
            description=f"System shutdown requested: {reason}",
            priority=100,  # CRITICAL priority
            status=TaskStatus.ACTIVE,  # Set as ACTIVE to prevent orphan deletion
            created_at=now_iso,
            updated_at=now_iso,
            context=context,
            parent_task_id=None,  # Root-level task
        )
        
        persistence.add_task(self.shutdown_task)
        logger.info(f"Created shutdown task: {self.shutdown_task.task_id}")
        
    async def _check_failure_reason(self, task: Task) -> Dict[str, Any]:
        """Check why the task failed - could be REJECT or actual error."""
        # Look at the final thought to determine reason
        thoughts = persistence.get_thoughts_by_task_id(task.task_id)
        if thoughts:
            # Get the most recent thought with a final action
            for thought in reversed(thoughts):
                if hasattr(thought, 'final_action') and thought.final_action:
                    action = thought.final_action
                    if isinstance(action, dict) and action.get('selected_action') == 'REJECT':
                        reason = action.get('action_parameters', {}).get('reason', 'No reason provided')
                        logger.warning(f"Agent REJECTED shutdown: {reason}")
                        # TODO: Implement human override flow
                        return {
                            "status": "rejected", 
                            "action": "shutdown_rejected",
                            "reason": reason,
                            "message": f"Agent rejected shutdown: {reason}"
                        }
        
        # Task failed for other reasons
        return {
            "status": "error",
            "action": "shutdown_error", 
            "message": "Shutdown task failed"
        }
    
    async def _process_shutdown_thoughts(self) -> None:
        """
        Process pending shutdown thoughts when called directly.
        This enables graceful shutdown when not in the main processing loop.
        """
        if not self.shutdown_task:
            return
            
        # Get pending thoughts for our shutdown task
        thoughts = persistence.get_thoughts_by_task_id(self.shutdown_task.task_id)
        pending_thoughts = [t for t in thoughts if t.status == ThoughtStatus.PENDING]
        
        if not pending_thoughts:
            return
            
        logger.info(f"Processing {len(pending_thoughts)} pending shutdown thoughts")
        
        for thought in pending_thoughts:
            try:
                # Mark as processing
                persistence.update_thought_status(
                    thought_id=thought.thought_id,
                    status=ThoughtStatus.PROCESSING
                )
                
                # Process through thought processor
                from ciris_engine.processor.processing_queue import ProcessingQueueItem
                item = ProcessingQueueItem.from_thought(thought)
                
                # Use our process_thought_item method to handle it
                result = await self.process_thought_item(item, context={"origin": "shutdown_direct"})
                
                if result:
                    # Dispatch the action
                    task = persistence.get_task_by_id(thought.source_task_id)
                    from ciris_engine.utils.context_utils import build_dispatch_context
                    
                    dispatch_context = build_dispatch_context(
                        thought=thought,
                        task=task,
                        app_config=self.app_config,
                        round_number=0,
                        action_type=result.selected_action if result else None
                    )
                    
                    await self.action_dispatcher.dispatch(
                        action_selection_result=result,
                        thought=thought,
                        dispatch_context=dispatch_context
                    )
                    
                    logger.info(f"Dispatched {result.selected_action} action for shutdown thought")
                else:
                    logger.warning(f"No result from processing shutdown thought {thought.thought_id}")
                    
            except Exception as e:
                logger.error(f"Error processing shutdown thought {thought.thought_id}: {e}", exc_info=True)
                persistence.update_thought_status(
                    thought_id=thought.thought_id,
                    status=ThoughtStatus.FAILED,
                    final_action={"error": str(e)}
                )
        
    async def cleanup(self) -> None:
        """Cleanup when transitioning out of SHUTDOWN state."""
        logger.info("Cleaning up shutdown processor")
        # Clear runtime shutdown context
        if self.runtime and hasattr(self.runtime, 'current_shutdown_context'):
            self.runtime.current_shutdown_context = None
        
