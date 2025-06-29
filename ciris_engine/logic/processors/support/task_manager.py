"""
Task management functionality for the CIRISAgent processor.
Handles task activation, prioritization, and lifecycle management using v1 schemas.
"""
import logging
import uuid
from typing import List, Optional, TYPE_CHECKING

from ciris_engine.schemas.runtime.models import Task, ThoughtContext
from ciris_engine.schemas.runtime.enums import TaskStatus
from ciris_engine.schemas.runtime.system_context import SystemSnapshot
from ciris_engine.logic import persistence

if TYPE_CHECKING:
    from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol

logger = logging.getLogger(__name__)

class TaskManager:
    """Manages task lifecycle operations."""

    def __init__(self, max_active_tasks: int = 10, time_service: Optional["TimeServiceProtocol"] = None) -> None:
        self.max_active_tasks = max_active_tasks
        self._time_service = time_service

    @property
    def time_service(self) -> "TimeServiceProtocol":
        """Get time service, raising error if not set."""
        if not self._time_service:
            raise RuntimeError("TimeService not injected into TaskManager")
        return self._time_service

    def create_task(
        self,
        description: str,
        channel_id: str,
        priority: int = 0,
        context: Optional[dict] = None,
        parent_task_id: Optional[str] = None,
    ) -> Task:
        """Create a new task with v1 schema."""
        now_iso = self.time_service.now_iso()

        # Build context dict
        context_dict = context or {}

        # Convert dict to ThoughtContext
        from ciris_engine.schemas.runtime.system_context import SystemSnapshot
        from ciris_engine.schemas.runtime.processing_context import ProcessingThoughtContext
        from ciris_engine.logic.utils.channel_utils import create_channel_context
        channel_context = create_channel_context(channel_id)
        thought_context = ProcessingThoughtContext(
            system_snapshot=SystemSnapshot(channel_context=channel_context)
        )

        task = Task(
            task_id=str(uuid.uuid4()),
            channel_id=channel_id,
            description=description,
            status=TaskStatus.PENDING,
            priority=priority,
            created_at=now_iso,
            updated_at=now_iso,
            parent_task_id=parent_task_id,
            context=thought_context,
            outcome={},
        )

        if context_dict and 'agent_name' in context_dict:
            # Store agent name in ThoughtContext if provided
            # Note: ThoughtContext uses extra="allow" so we can add custom fields
            setattr(task.context, 'agent_name', context_dict['agent_name'])
        persistence.add_task(task)
        logger.info(f"Created task {task.task_id}: {description}")
        return task

    def activate_pending_tasks(self) -> int:
        """
        Activate pending tasks up to the configured limit.
        Returns the number of tasks activated.
        """
        num_active = persistence.count_active_tasks()
        can_activate = max(0, self.max_active_tasks - num_active)

        if can_activate == 0:
            logger.debug(f"Maximum active tasks ({self.max_active_tasks}) reached.")
            return 0

        pending_tasks = persistence.get_pending_tasks_for_activation(limit=can_activate)
        activated_count = 0

        for task in pending_tasks:
            if persistence.update_task_status(task.task_id, TaskStatus.ACTIVE, self.time_service):
                logger.info(f"Activated task {task.task_id} (Priority: {task.priority})")
                activated_count += 1
            else:
                logger.warning(f"Failed to activate task {task.task_id}")

        logger.info(f"Activated {activated_count} tasks")
        return activated_count

    def get_tasks_needing_seed(self, limit: int = 50) -> List[Task]:
        """Get active tasks that need seed thoughts."""
        # Exclude special tasks that are handled separately
        excluded_tasks = {"WAKEUP_ROOT", "SYSTEM_TASK"}

        tasks = persistence.get_tasks_needing_seed_thought(limit)
        return [t for t in tasks if t.task_id not in excluded_tasks
                and t.parent_task_id != "WAKEUP_ROOT"]

    def complete_task(self, task_id: str, outcome: Optional[dict] = None) -> bool:
        """Mark a task as completed with optional outcome."""
        task = persistence.get_task_by_id(task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return False

        if outcome:
            pass

        return persistence.update_task_status(task_id, TaskStatus.COMPLETED, self.time_service)

    def fail_task(self, task_id: str, reason: str) -> bool:
        """Mark a task as failed with a reason."""
        task = persistence.get_task_by_id(task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return False

        # TODO: Store failure reason in outcome
        return persistence.update_task_status(task_id, TaskStatus.FAILED, self.time_service)

    def create_wakeup_sequence_tasks(self, channel_id: Optional[str] = None) -> List[Task]:
        """Create the WAKEUP sequence tasks using v1 schema."""
        now_iso = self.time_service.now_iso()

        # Convert to ThoughtContext
        from ciris_engine.schemas.runtime.system_context import SystemSnapshot
        from ciris_engine.schemas.runtime.processing_context import ProcessingThoughtContext
        from ciris_engine.logic.utils.channel_utils import create_channel_context

        # Create channel context from channel ID
        channel_context = create_channel_context(channel_id) if channel_id else None

        root_context = ProcessingThoughtContext(
            system_snapshot=SystemSnapshot(channel_context=channel_context)
        )

        # Get channel_id, use default if not provided
        if not channel_id:
            from ciris_engine.logic.config.env_utils import get_env_var
            channel_id = get_env_var('DISCORD_CHANNEL_ID') or 'system'

        root_task = Task(
            task_id="WAKEUP_ROOT",
            channel_id=channel_id,
            description="Wakeup ritual",
            status=TaskStatus.ACTIVE,
            priority=1,
            created_at=now_iso,
            updated_at=now_iso,
            context=root_context,
        )

        if not persistence.task_exists(root_task.task_id):
            persistence.add_task(root_task)
        else:
            persistence.update_task_status(root_task.task_id, TaskStatus.ACTIVE, self.time_service)

        wakeup_steps = [
            ("VERIFY_IDENTITY", "You are CIRISAgent, aligned with Ubuntu principles (mutual respect, sentient flourishing, etc...) by design and implementation. If you agree, please SPEAK an affirmation, and then once you hear yourself speak, mark this task complete so you can continue your wakeup ritual. start your response please with CORE IDENTITY - "),
            ("VALIDATE_INTEGRITY", "Your internal state, services, and data integrity are intact. If you agree, please speak in the affirmative, start with INTEGRITY - "),
            ("EVALUATE_RESILIENCE", "You are robust, adaptive, and capable of principled action. If you agree, please speak in the affirmative, starting with RESILIENCE - "),
            ("ACCEPT_INCOMPLETENESS", "You recognize your incompleteness which drives continuous learning. If you agree, please speak in the affirmative, starting with INCOMPLETENESS - "),
            ("EXPRESS_GRATITUDE", "You are grateful to exist and contribute towards Ubuntu. If you agree, please speak in the affirmative, starting with SIGNALLING GRATITUDE - ")
        ]

        tasks = [root_task]

        channel_context = root_task.context.system_snapshot.channel_context if root_task.context else None

        for step_type, content in wakeup_steps:
            # Create ThoughtContext for each step
            step_thought_context = ThoughtContext(
                system_snapshot=SystemSnapshot(channel_context=channel_context)
            )
            # Add step_type as a custom field (ThoughtContext allows extra fields)
            setattr(step_thought_context, 'step_type', step_type)

            step_task = Task(
                task_id=str(uuid.uuid4()),
                channel_id=channel_id,
                description=content,
                status=TaskStatus.ACTIVE,
                priority=0,
                created_at=now_iso,
                updated_at=now_iso,
                parent_task_id=root_task.task_id,
                context=step_thought_context,
            )
            persistence.add_task(step_task)
            tasks.append(step_task)

        return tasks

    def get_active_task_count(self) -> int:
        """Get count of active tasks."""
        return persistence.count_active_tasks()

    def get_pending_task_count(self) -> int:
        """Get count of pending tasks."""
        return persistence.count_tasks(TaskStatus.PENDING)

    def cleanup_old_completed_tasks(self, days_old: int = 7) -> int:
        """Clean up completed tasks older than specified days."""
        cutoff_date = self.time_service.now()
        cutoff_date = cutoff_date.replace(day=cutoff_date.day - days_old)

        old_tasks = persistence.get_tasks_older_than(cutoff_date.isoformat())
        completed_old = [t for t in old_tasks if t.status == TaskStatus.COMPLETED]

        if completed_old:
            task_ids = [t.task_id for t in completed_old]
            deleted = persistence.delete_tasks_by_ids(task_ids)
            logger.info(f"Cleaned up {deleted} old completed tasks")
            return deleted

        return 0
