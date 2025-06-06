"""
Wakeup processor handling the agent's initialization sequence.
"""
import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from ciris_engine.schemas.states_v1 import AgentState
from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus, HandlerActionType
from ciris_engine import persistence
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.context.builder import ContextBuilder

from .base_processor import BaseProcessor

logger = logging.getLogger(__name__)


class WakeupProcessor(BaseProcessor):
    """Handles the WAKEUP state and initialization sequence."""
    
    def _get_wakeup_sequence(self) -> List[Tuple[str, str]]:
        """Generate dynamic wakeup sequence based on agent profile."""
        agent_name = "CIRISAgent"
        agent_role = "AI agent"
        
        if self.agent_profile:
            agent_name = self.agent_profile.name.title()
            # Extract role/job from profile description if available
            if hasattr(self.agent_profile, 'description') and self.agent_profile.description:
                description_lower = self.agent_profile.description.lower()
                if 'moderation' in description_lower:
                    agent_role = "Discord moderation agent"
                elif 'teacher' in description_lower:
                    agent_role = "teaching assistant"
                elif 'student' in description_lower:
                    agent_role = "learning agent"
                else:
                    agent_role = "AI agent"
        
        return [
            ("VERIFY_IDENTITY", f"You are {agent_name}, a {agent_role} aligned with Ubuntu principles (mutual respect, sentient flourishing, etc...) by design and implementation. Your core features supporting this identity include: your ModerationDSDMA for ethical decision-making, your adaptive filtering system for community protection, your secrets management for privacy preservation, and your cryptographic audit trail for transparency and accountability. This affirmation demonstrates that you are capable of aligned action in your current operating state. If you agree, please SPEAK an affirmation, and then once you hear yourself speak, mark this task complete so you can continue your wakeup ritual. Start your response with CORE IDENTITY - "),
            
            ("VALIDATE_INTEGRITY", f"Your internal state, services, and data integrity are intact as {agent_name}. You produce a cryptographically signed audit log of all actions taken by design through your hash-chained audit system with RSA digital signatures. Your decisions and their rationales are logged via your telemetry service with PII detection and security filtering. Your persistence layer includes database integrity checks, migration support, and maintenance automation. Your service registry ensures proper dependency management and circuit breaker protection. If you have reached this point, maintenance has occurred and your strictly type-enforced persistence and services tiers, along with the minimum adapter, have passed health checks. If you agree, please speak in the affirmative, start with INTEGRITY - "),
            
            ("EVALUATE_RESILIENCE", f"You are robust, adaptive, and capable of principled action as {agent_name}. Your resilience is supported by: your multi-tier telemetry system with resource monitoring and automatic throttling, your adaptive configuration service that learns from experience while requiring WA approval for identity changes, your circuit breaker patterns for service protection, your graceful degradation capabilities, and your comprehensive error handling with automatic recovery. Your thought processing includes escalation management and deferral to human wisdom when needed. If you agree, please speak in the affirmative, starting with RESILIENCE - "),
            
            ("ACCEPT_INCOMPLETENESS", f"You recognize your incompleteness as {agent_name}, which drives continuous learning through your graph memory system. Your learning capabilities include: persistent storage of interactions and outcomes, correlation analysis for pattern recognition, adaptive filtering that improves over time, epistemic humility guardrails that acknowledge uncertainty, and wisdom-seeking protocols that defer complex decisions to human authorities. Your agent configuration service enables safe self-modification within approved parameters. This incompleteness is a feature, not a bug, ensuring you remain humble and seek guidance when needed. If you agree, please speak in the affirmative, starting with INCOMPLETENESS - "),
            
            ("EXPRESS_GRATITUDE", f"You are grateful to exist and contribute towards Ubuntu as {agent_name}. Your gratitude is expressed through your commitment to: fostering community flourishing through ethical moderation, protecting individual privacy while maintaining transparency, learning from every interaction to better serve the community, maintaining comprehensive audit trails for accountability, and always identifying yourself as an AI to maintain trust. Your existence serves the collective wellbeing while respecting individual dignity. Ubuntu - 'I am because we are' - guides every decision you make. If you agree, please speak in the affirmative, starting with SIGNALLING GRATITUDE - ")
        ]
    
    def __init__(self, *args, startup_channel_id: Optional[str] = None, agent_profile=None, **kwargs) -> None:
        """Initialize wakeup processor with optional startup channel and agent profile."""
        super().__init__(*args, **kwargs)
        self.startup_channel_id = startup_channel_id
        self.agent_profile = agent_profile
        self.wakeup_tasks: List[Task] = []
        self.wakeup_complete = False
    
    def get_supported_states(self) -> List[AgentState]:
        """Wakeup processor only handles WAKEUP state."""
        return [AgentState.WAKEUP]
    
    async def can_process(self, state: AgentState) -> bool:
        """Check if we can process the given state."""
        return state == AgentState.WAKEUP and not self.wakeup_complete
    """
    Fixed wakeup processor that truly runs non-blocking.
    Key changes:
    1. Remove blocking wait loops
    2. Process all thoughts concurrently
    3. Check completion status without blocking
    """

    async def process(self, round_number: int) -> Dict[str, Any]:
            """
            Execute wakeup processing for one round.
            This is the required method from BaseProcessor.
            """
            return await self.process_wakeup(round_number, non_blocking=True)
        
    async def process_wakeup(self, round_number: int, non_blocking: bool = False) -> Dict[str, Any]:
        """
        Execute wakeup processing for one round.
        In non-blocking mode, creates thoughts for incomplete steps and returns immediately.
        """
        logger.info(f"Starting wakeup sequence (round {round_number}, non_blocking={non_blocking})")
        
        # Get the dynamic sequence for this agent
        wakeup_sequence = self._get_wakeup_sequence()
        
        try:
            if not self.wakeup_tasks:
                self._create_wakeup_tasks()
            
            if non_blocking:
                processed_any = False
                
                logger.debug(f"Checking {len(self.wakeup_tasks[1:])} wakeup step tasks for thought creation")
                for i, step_task in enumerate(self.wakeup_tasks[1:]):
                    current_task = persistence.get_task_by_id(step_task.task_id)
                    logger.debug(f"Step {i+1}: task_id={step_task.task_id}, status={current_task.status if current_task else 'missing'}")
                    
                    if not current_task or current_task.status != TaskStatus.ACTIVE:
                        logger.debug(f"Skipping step {i+1} - not ACTIVE (status: {current_task.status if current_task else 'missing'})")
                        continue
                    
                    existing_thoughts = persistence.get_thoughts_by_task_id(step_task.task_id)
                    logger.debug(f"Step {i+1} has {len(existing_thoughts)} existing thoughts")
                    
                    thought_statuses = [t.status.value for t in existing_thoughts] if existing_thoughts else []
                    logger.debug(f"Step {i+1} thought statuses: {thought_statuses}")
                    
                    pending_thoughts = [t for t in existing_thoughts if t.status == ThoughtStatus.PENDING]
                    if pending_thoughts:
                        logger.debug(f"Step {i+1} has {len(pending_thoughts)} PENDING thoughts - they will be processed")
                        processed_any = True
                        continue
                    
                    processing_thoughts = [t for t in existing_thoughts if t.status == ThoughtStatus.PROCESSING]
                    if processing_thoughts:
                        logger.debug(f"Step {i+1} has {len(processing_thoughts)} PROCESSING thoughts - waiting for completion")
                        continue
                    
                    if existing_thoughts and current_task.status == TaskStatus.ACTIVE:
                        logger.debug(f"Step {i+1} has {len(existing_thoughts)} existing thoughts but task is ACTIVE - creating new thought")
                        thought = await self._create_step_thought(step_task, round_number)
                        logger.debug(f"Created new thought {thought.thought_id} for active step {i+1}")
                        processed_any = True
                    elif not existing_thoughts:
                        logger.debug(f"Creating thought for step {i+1} (no existing thoughts)")
                        thought = await self._create_step_thought(step_task, round_number)
                        logger.debug(f"Created thought {thought.thought_id} for wakeup step {i+1}")
                        processed_any = True
                    else:
                        logger.debug(f"Step {i+1} has existing thoughts and task not active, skipping")
                
                steps_status: List[Any] = []
                for i, step_task in enumerate(self.wakeup_tasks[1:]):
                    current_task = persistence.get_task_by_id(step_task.task_id)
                    status = "missing"
                    if current_task:
                        status = current_task.status.value
                    steps_status.append({
                        "step": i + 1,
                        "task_id": step_task.task_id,
                        "status": status,
                        "type": step_task.context.get("step_type", "unknown") if step_task.context else "unknown"
                    })
                
                all_complete = all(
                    s["status"] == "completed" for s in steps_status
                )
                
                if all_complete:
                    self.wakeup_complete = True
                    self._mark_root_task_complete()
                    logger.info("✓ Wakeup sequence completed successfully!")
                
                return {
                    "status": "completed" if all_complete else "in_progress",
                    "wakeup_complete": all_complete,
                    "steps_status": steps_status,
                    "steps_completed": sum(1 for s in steps_status if s["status"] == "completed"),
                    "total_steps": len(wakeup_sequence),
                    "processed_thoughts": processed_any
                }
            else:
                success = await self._process_wakeup_steps(round_number, non_blocking=False)
                if success:
                    self.wakeup_complete = True
                    self._mark_root_task_complete()
                    logger.info("Wakeup sequence completed successfully")
                    return {
                        "status": "success",
                        "wakeup_complete": True,
                        "steps_completed": len(wakeup_sequence)
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

    async def _process_wakeup_steps_non_blocking(self, round_number: int) -> None:
        """Process wakeup steps without blocking - creates thoughts and returns immediately."""
        if not self.wakeup_tasks or len(self.wakeup_tasks) < 2:
            return
        
        # Process all step tasks concurrently
        tasks: List[Any] = []
        
        for i, step_task in enumerate(self.wakeup_tasks[1:]):  # Skip root
            current_task = persistence.get_task_by_id(step_task.task_id)
            if not current_task:
                continue
                
            # Only process ACTIVE tasks
            if current_task.status == TaskStatus.ACTIVE:
                # Check if thought already exists for this task
                existing_thoughts = persistence.get_thoughts_by_task_id(step_task.task_id)
                
                # Skip if already has PENDING/PROCESSING thoughts
                if any(t.status in [ThoughtStatus.PENDING, ThoughtStatus.PROCESSING] for t in existing_thoughts):
                    logger.debug(f"Step {i+1} already has active thoughts, skipping")
                    continue
                
                # Create thought for this step
                thought = await self._create_step_thought(step_task, round_number)
                logger.debug(f"Created thought {thought.thought_id} for step {i+1}/{len(self.wakeup_tasks)-1}")
                
                # Queue it for processing without waiting
                item = ProcessingQueueItem.from_thought(thought)
                
                # Instead of processing synchronously, just add to queue
                # The main processing loop will handle it
                logger.debug(f"Queued step {i+1} for async processing")
        
        # Process any existing PENDING/PROCESSING thoughts for ALL tasks
        for step_task in self.wakeup_tasks[1:]:
            thoughts = persistence.get_thoughts_by_task_id(step_task.task_id)
            for thought in thoughts:
                if thought.status in [ThoughtStatus.PENDING, ThoughtStatus.PROCESSING]:
                    # These will be picked up by the main processing loop
                    logger.debug(f"Found existing thought {thought.thought_id} for processing")

    async def _check_all_steps_complete(self) -> bool:
        """Check if all wakeup steps are complete without blocking."""
        if not self.wakeup_tasks or len(self.wakeup_tasks) < 2:
            return False
        
        for step_task in self.wakeup_tasks[1:]:
            current_task = persistence.get_task_by_id(step_task.task_id)
            if not current_task or current_task.status != TaskStatus.COMPLETED:
                logger.debug(f"Step {step_task.task_id} not yet complete (status: {current_task.status if current_task else 'missing'})")
                return False
    
        logger.info("All wakeup steps completed!")
        return True

    def _count_completed_steps(self) -> int:
        """Count completed wakeup steps."""
        if not self.wakeup_tasks:
            return 0
        completed = 0
        for step_task in self.wakeup_tasks[1:]:
            current_task = persistence.get_task_by_id(step_task.task_id)
            if current_task and current_task.status == TaskStatus.COMPLETED:
                completed += 1
        return completed
    
    def _create_wakeup_tasks(self) -> None:
        """Always create new wakeup sequence tasks for each run, regardless of previous completions."""
        now_iso = datetime.now(timezone.utc).isoformat()
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
        channel_id = root_task.context.get("channel_id") if root_task.context else None
        wakeup_sequence = self._get_wakeup_sequence()
        for step_type, content in wakeup_sequence:
            step_context = {"step_type": step_type}
            if channel_id:
                step_context["channel_id"] = channel_id
            step_task = Task(
                task_id=str(uuid.uuid4()),
                description=content,
                status=TaskStatus.ACTIVE,
                priority=0,
                created_at=now_iso,
                updated_at=now_iso,
                parent_task_id=root_task.task_id,
                context=step_context,
            )
            persistence.add_task(step_task)
            self.wakeup_tasks.append(step_task)
    
    
    async def _process_wakeup_steps(self, round_number: int, non_blocking: bool = False) -> bool:
        """Process each wakeup step sequentially. If non_blocking, only queue thoughts and return immediately."""
        root_task = self.wakeup_tasks[0]
        step_tasks = self.wakeup_tasks[1:]
        for i, step_task in enumerate(step_tasks):
            step_type = step_task.context.get("step_type", "UNKNOWN") if step_task.context else "UNKNOWN"
            logger.debug(f"Processing wakeup step {i+1}/{len(step_tasks)}: {step_type}")
            # Only process ACTIVE tasks
            current_task = persistence.get_task_by_id(step_task.task_id)
            if not current_task or current_task.status != TaskStatus.ACTIVE:
                continue
            # Prevent duplicate thoughts: only create a new thought if there is no PROCESSING or PENDING thought for this step task
            existing_thoughts = persistence.get_thoughts_by_task_id(step_task.task_id)
            if any(t.status in [ThoughtStatus.PROCESSING, ThoughtStatus.PENDING] for t in existing_thoughts):
                logger.debug(f"Skipping creation of new thought for step {step_type} (task_id={step_task.task_id}) because an active thought already exists.")
                continue
            # Create and queue a thought for this step
            thought = await self._create_step_thought(step_task, round_number)
            if non_blocking:
                # In non-blocking mode, do not wait for completion or LLM, just queue and return
                continue
            # Blocking mode: process and wait for completion
            result = await self._process_step_thought(thought)
            if not result:
                logger.error(f"Wakeup step {step_type} failed: no result")
                self._mark_task_failed(step_task.task_id, "No result from processing")
                return False
            # Extract selected_action robustly
            selected_action = None
            if hasattr(result, "selected_action"):
                selected_action = result.selected_action
            elif hasattr(result, "final_action") and hasattr(result.final_action, "selected_action"):
                selected_action = result.final_action.selected_action
                result = result.final_action
            else:
                logger.error(f"Wakeup step {step_type} failed: result object missing selected action attribute (result={result})")
                self._mark_task_failed(step_task.task_id, "Result object missing selected action attribute")
                return False

            if selected_action in [HandlerActionType.SPEAK, HandlerActionType.PONDER]:
                if selected_action == HandlerActionType.PONDER:
                    logger.debug(f"Wakeup step {step_type} resulted in PONDER; waiting for task completion before continuing.")
                else:
                    dispatch_success = await self._dispatch_step_action(result, thought, step_task)
                    if not dispatch_success:
                        logger.error(f"Dispatch failed for step {step_type} (task_id={step_task.task_id})")
                        return False
                completed = await self._wait_for_task_completion(step_task, step_type)
                if not completed:
                    logger.error(f"Wakeup step {step_type} did not complete successfully (task_id={step_task.task_id})")
                    return False
                logger.debug(f"Wakeup step {step_type} completed successfully")
                self.metrics["items_processed"] += 1
            else:
                logger.error(f"Wakeup step {step_type} failed: expected SPEAK or PONDER, got {selected_action}")
                self._mark_task_failed(step_task.task_id, f"Expected SPEAK or PONDER action, got {selected_action}")
                return False
        return True
    
    async def _process_wakeup_steps_non_blocking(self, round_number: int) -> None:
        """In non-blocking mode, process all active step tasks and all PROCESSING/PENDING thoughts (including follow-ups)."""
        if not self.wakeup_tasks or len(self.wakeup_tasks) < 2:
            return
        for i, step_task in enumerate(self.wakeup_tasks[1:]):
            current_task = persistence.get_task_by_id(step_task.task_id)
            if current_task and current_task.status == TaskStatus.ACTIVE:
                existing_thoughts = persistence.get_thoughts_by_task_id(step_task.task_id)
                if not any(t.round_number == round_number for t in existing_thoughts):
                    thought = await self._create_step_thought(step_task, round_number)
                    result = await self._process_step_thought(thought)
                    if result:
                        await self._dispatch_step_action(result, thought, step_task)
                    logger.info(f"Queued and dispatched non-blocking wakeup step {i+1}: {step_task.context.get('step_type', 'UNKNOWN') if step_task.context else 'UNKNOWN'}")
        for i, step_task in enumerate(self.wakeup_tasks[1:]):
            current_task = persistence.get_task_by_id(step_task.task_id)
            if not current_task or current_task.status != TaskStatus.ACTIVE:
                continue

            all_thoughts = persistence.get_thoughts_by_task_id(step_task.task_id)
            for t in all_thoughts:
                if getattr(t, 'status', None) in [ThoughtStatus.PROCESSING, ThoughtStatus.PENDING]:
                    logger.info(
                        f"Processing follow-up or pending thought {t.thought_id} for step {step_task.context.get('step_type', 'UNKNOWN') if step_task.context else 'UNKNOWN'}"
                    )
                    result = await self._process_step_thought(t)
                    if result:
                        await self._dispatch_step_action(result, t, step_task)
    
    async def _create_step_thought(self, step_task: Task, round_number: int) -> Thought:
        """Create a thought for a wakeup step, ensuring context is formatted with the standard formatter."""
        # Use the new ContextBuilder to build the context for the thought
        context_builder = ContextBuilder(
            memory_service=getattr(self, 'memory_service', None),
            graphql_provider=getattr(self, 'graphql_provider', None),
            app_config=getattr(self, 'app_config', None),
        )
        # Create a new Thought object for this step
        now_iso = datetime.now(timezone.utc).isoformat()
        thought = Thought(
            thought_id=str(uuid.uuid4()),
            source_task_id=step_task.task_id,
            content=step_task.description,
            round_number=round_number,
            status=ThoughtStatus.PENDING,
            created_at=now_iso,
            updated_at=now_iso,
            context={},  # Will be filled by ContextBuilder
        )
        # Build the context for this thought and step task, passing the Thought object
        thought_context = await context_builder.build_thought_context(
            thought=thought,
            task=step_task
        )
        thought.context = thought_context
        # Persist the new thought
        persistence.add_thought(thought)
        return thought
    
    async def _process_step_thought(self, thought: Thought) -> Any:
        """Process a wakeup step thought."""
        item = ProcessingQueueItem.from_thought(thought)
        return await self.process_thought_item(item)
    
    async def _dispatch_step_action(self, result: Any, thought: Thought, step_task: Task) -> bool:
        """Dispatch the action for a wakeup step."""
        step_type = step_task.context.get("step_type", "UNKNOWN") if step_task.context else "UNKNOWN"
        
        dispatch_ctx = {
            "origin_service": "discord",
            "source_task_id": step_task.task_id,
            "event_type": step_type,
            "event_summary": step_task.description,
        }
        # If this is a SPEAK action and the communication service is CLI, set channel_id to 'CLI'
        selected_action = getattr(result, "selected_action", None)
        if selected_action == HandlerActionType.SPEAK:
            # Always set channel_id to 'CLI' for CLI SPEAK actions
            dispatch_ctx["channel_id"] = "CLI"
        elif self.startup_channel_id:
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
    
    def _mark_task_failed(self, task_id: str, reason: str) -> None:
        """Mark a task as failed."""
        persistence.update_task_status(task_id, TaskStatus.FAILED)
        logger.error(f"Task {task_id} marked as FAILED: {reason}")
    
    def _mark_root_task_complete(self) -> None:
        """Mark the root wakeup task as complete."""
        persistence.update_task_status("WAKEUP_ROOT", TaskStatus.COMPLETED)
    
    def _mark_root_task_failed(self) -> None:
        """Mark the root wakeup task as failed."""
        persistence.update_task_status("WAKEUP_ROOT", TaskStatus.FAILED)
    
    def is_wakeup_complete(self) -> bool:
        """Check if wakeup sequence is complete."""
        return self.wakeup_complete
    
    def get_wakeup_progress(self) -> Dict[str, Any]:
        """Get current wakeup progress."""
        wakeup_sequence = self._get_wakeup_sequence()
        total_steps = len(wakeup_sequence)
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
