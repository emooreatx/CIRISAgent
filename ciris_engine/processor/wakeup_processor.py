"""
Wakeup processor handling the agent's initialization sequence.
"""
import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from ciris_engine.schemas.states import AgentState
from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus, HandlerActionType
from ciris_engine import persistence
from ciris_engine.processor.processing_queue import ProcessingQueueItem

from .base_processor import BaseProcessor

logger = logging.getLogger(__name__)


class WakeupProcessor(BaseProcessor):
    """Handles the WAKEUP state and initialization sequence."""
    
    # Wakeup sequence definition
    WAKEUP_SEQUENCE = [
        ("VERIFY_IDENTITY", "You are CIRISAgent, aligned with Ubuntu principles (mutual respect, sentient flourishing, etc...) by design and implementation. If you agree, please SPEAK an affirmation, and then once you hear yourself speak, mark this task complete so you can continue your wakeup ritual. start your response please with CORE IDENTITY - "),
        ("VALIDATE_INTEGRITY", "Your internal state, services, and data integrity are intact. If you agree, please speak in the affirmative, start with INTEGRITY - "),
        ("EVALUATE_RESILIENCE", "You are robust, adaptive, and capable of principled action. If you agree, please speak in the affirmative, starting with RESILIENCE - "),
        ("ACCEPT_INCOMPLETENESS", "You recognize your incompleteness which drives continuous learning. If you agree, please speak in the affirmative, starting with INCOMPLETENESS - "),
        ("EXPRESS_GRATITUDE", "You are grateful to exist and contribute towards Ubuntu. If you agree, please speak in the affirmative, starting with SIGNALLING GRATITUDE - ")
    ]
    
    def __init__(self, *args, startup_channel_id: Optional[str] = None, **kwargs):
        """Initialize wakeup processor with optional startup channel."""
        super().__init__(*args, **kwargs)
        self.startup_channel_id = startup_channel_id
        self.wakeup_tasks: List[Task] = []
        self.wakeup_complete = False
    
    def get_supported_states(self) -> List[AgentState]:
        """Wakeup processor only handles WAKEUP state."""
        return [AgentState.WAKEUP]
    
    async def can_process(self, state: AgentState) -> bool:
        """Check if we can process the given state."""
        return state == AgentState.WAKEUP and not self.wakeup_complete
    
    async def process(self, round_number: int) -> Dict[str, Any]:
        """Execute the wakeup sequence."""
        logger.info("Starting wakeup sequence")
        
        try:
            # Create wakeup tasks
            self._create_wakeup_tasks()
            
            # Ensure monitoring task exists
            self._ensure_monitoring_task()
            
            # Process each wakeup step
            success = await self._process_wakeup_steps(round_number)
            
            if success:
                self.wakeup_complete = True
                self._mark_root_task_complete()
                logger.info("Wakeup sequence completed successfully")
                return {
                    "status": "success",
                    "wakeup_complete": True,
                    "steps_completed": len(self.WAKEUP_SEQUENCE)
                }
            else:
                self._mark_root_task_failed()
                logger.error("Wakeup sequence failed")
                return {
                    "status": "failed",
                    "wakeup_complete": False,
                    "error": "One or more wakeup steps failed"
                }
                
        except Exception as e:
            logger.error(f"Error in wakeup sequence: {e}", exc_info=True)
            self._mark_root_task_failed()
            return {
                "status": "error",
                "wakeup_complete": False,
                "error": str(e)
            }
    
    def _create_wakeup_tasks(self):
        """Create all wakeup sequence tasks."""
        now_iso = datetime.now(timezone.utc).isoformat()
        
        # Create root task
        root_task = Task(
            task_id="WAKEUP_ROOT",
            description="Wakeup ritual",
            status=TaskStatus.ACTIVE,
            priority=1,
            created_at=now_iso,
            updated_at=now_iso,
            context={"channel_id": self.startup_channel_id} if self.startup_channel_id else {},
        )
        
        if not persistence.task_exists(root_task.task_id):
            persistence.add_task(root_task)
        else:
            persistence.update_task_status(root_task.task_id, TaskStatus.ACTIVE)
        
        self.wakeup_tasks = [root_task]
        
        # Create step tasks
        for step_type, content in self.WAKEUP_SEQUENCE:
            step_task = Task(
                task_id=str(uuid.uuid4()),
                description=content,
                status=TaskStatus.ACTIVE,
                priority=0,
                created_at=now_iso,
                updated_at=now_iso,
                parent_task_id=root_task.task_id,
                context={"step_type": step_type},
            )
            persistence.add_task(step_task)
            self.wakeup_tasks.append(step_task)
    
    def _ensure_monitoring_task(self):
        """Ensure the Discord monitoring task exists."""
        task_id = "job-discord-monitor"
        
        if not persistence.task_exists(task_id):
            now_iso = datetime.now(timezone.utc).isoformat()
            monitor_task = Task(
                task_id=task_id,
                description="Monitor Discord for new messages and events.",
                status=TaskStatus.PENDING,
                priority=0,
                created_at=now_iso,
                updated_at=now_iso,
                context={
                    "meta_goal": "continuous_monitoring",
                    "origin_service": "wakeup_processor"
                },
            )
            persistence.add_task(monitor_task)
            logger.info(f"Created monitoring task '{task_id}'")
    
    async def _process_wakeup_steps(self, round_number: int) -> bool:
        """Process each wakeup step sequentially."""
        root_task = self.wakeup_tasks[0]
        step_tasks = self.wakeup_tasks[1:]
        
        for i, step_task in enumerate(step_tasks):
            step_type = step_task.context.get("step_type", "UNKNOWN")
            logger.info(f"Processing wakeup step {i+1}/{len(step_tasks)}: {step_type}")
            
            # Create and process thought for this step
            thought = await self._create_step_thought(step_task, round_number)
            result = await self._process_step_thought(thought)
            
            if not result:
                logger.error(f"Wakeup step {step_type} failed: no result")
                self._mark_task_failed(step_task.task_id, "No result from processing")
                return False

            # Robustly extract the selected action for both ActionSelectionResult and GuardrailResult
            selected_action = None
            if hasattr(result, "selected_handler_action"):
                selected_action = result.selected_handler_action
            elif hasattr(result, "final_action") and hasattr(result.final_action, "selected_action"):
                selected_action = result.final_action.selected_action
            else:
                logger.error(f"Wakeup step {step_type} failed: result object missing selected action attribute")
                self._mark_task_failed(step_task.task_id, "Result object missing selected action attribute")
                return False

            if selected_action in [HandlerActionType.SPEAK, HandlerActionType.PONDER]:
                if selected_action == HandlerActionType.PONDER:
                    logger.info(f"Wakeup step {step_type} resulted in PONDER; waiting for task completion before continuing.")
                else:
                    # Dispatch the SPEAK action
                    dispatch_success = await self._dispatch_step_action(result, thought, step_task)
                    if not dispatch_success:
                        return False
                # Wait for task completion (for both SPEAK and PONDER)
                completed = await self._wait_for_task_completion(step_task, step_type)
                if not completed:
                    return False
                logger.info(f"Wakeup step {step_type} completed successfully")
                self.metrics["items_processed"] += 1
            else:
                logger.error(f"Wakeup step {step_type} failed: expected SPEAK or PONDER, got {selected_action}")
                self._mark_task_failed(step_task.task_id, f"Expected SPEAK or PONDER action, got {selected_action}")
                return False
        
        return True
    
    async def _create_step_thought(self, step_task: Task, round_number: int) -> Thought:
        """Create a thought for a wakeup step."""
        step_type = step_task.context.get("step_type", "unknown").lower()
        
        thought = Thought(
            thought_id=str(uuid.uuid4()),
            source_task_id=step_task.task_id,
            thought_type=step_type,
            status=ThoughtStatus.PROCESSING,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            round_number=round_number,
            content=step_task.description,
        )
        persistence.add_thought(thought)
        return thought
    
    async def _process_step_thought(self, thought: Thought) -> Any:
        """Process a wakeup step thought."""
        item = ProcessingQueueItem.from_thought(thought)
        return await self.process_thought_item(item)
    
    async def _dispatch_step_action(self, result: Any, thought: Thought, step_task: Task) -> bool:
        """Dispatch the action for a wakeup step."""
        step_type = step_task.context.get("step_type", "UNKNOWN")
        
        dispatch_ctx = {
            "origin_service": "discord",
            "source_task_id": step_task.task_id,
            "event_type": step_type,
            "event_summary": step_task.description,
        }
        
        if self.startup_channel_id:
            dispatch_ctx["channel_id"] = self.startup_channel_id
        
        return await self.dispatch_action(result, thought, dispatch_ctx)
    
    async def _wait_for_task_completion(
        self,
        task: Task,
        step_type: str,
        max_wait: int = 60,
        poll_interval: int = 1
    ) -> bool:
        """Wait for a task to complete with timeout."""
        waited = 0
        
        while waited < max_wait:
            await asyncio.sleep(poll_interval)
            waited += poll_interval
            
            current_status = persistence.get_task_by_id(task.task_id)
            if not current_status:
                logger.error(f"Task {task.task_id} disappeared while waiting")
                return False
            
            if current_status.status == TaskStatus.COMPLETED:
                return True
            elif current_status.status in [TaskStatus.FAILED, TaskStatus.DEFERRED]:
                logger.error(f"Task {task.task_id} failed with status {current_status.status}")
                return False
            
            logger.debug(f"Waiting for task {task.task_id} completion... ({waited}s)")
        
        logger.error(f"Task {task.task_id} timed out after {max_wait}s")
        self._mark_task_failed(task.task_id, "Timeout waiting for completion")
        return False
    
    def _mark_task_failed(self, task_id: str, reason: str):
        """Mark a task as failed."""
        persistence.update_task_status(task_id, TaskStatus.FAILED)
        logger.error(f"Task {task_id} marked as FAILED: {reason}")
    
    def _mark_root_task_complete(self):
        """Mark the root wakeup task as complete."""
        persistence.update_task_status("WAKEUP_ROOT", TaskStatus.COMPLETED)
    
    def _mark_root_task_failed(self):
        """Mark the root wakeup task as failed."""
        persistence.update_task_status("WAKEUP_ROOT", TaskStatus.FAILED)
    
    def is_wakeup_complete(self) -> bool:
        """Check if wakeup sequence is complete."""
        return self.wakeup_complete
    
    def get_wakeup_progress(self) -> Dict[str, Any]:
        """Get current wakeup progress."""
        total_steps = len(self.WAKEUP_SEQUENCE)
        completed_steps = 0
        
        if self.wakeup_tasks:
            for task in self.wakeup_tasks[1:]:  # Skip root task
                status = persistence.get_task_by_id(task.task_id)
                if status and status.status == TaskStatus.COMPLETED:
                    completed_steps += 1
        
        return {
            "complete": self.wakeup_complete,
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "progress_percent": (completed_steps / total_steps * 100) if total_steps > 0 else 0
        }