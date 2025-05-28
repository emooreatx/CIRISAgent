"""
Task management functionality for the CIRISAgent processor.
Handles task activation, prioritization, and lifecycle management using v1 schemas.
"""
import logging
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from ciris_engine.schemas.agent_core_schemas_v1 import Task
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus
from ciris_engine import persistence

logger = logging.getLogger(__name__)


class TaskManager:
    """Manages task lifecycle operations."""
    
    def __init__(self, max_active_tasks: int = 10):
        self.max_active_tasks = max_active_tasks
        
    def create_task(
        self,
        description: str,
        priority: int = 0,
        context: Optional[Dict[str, Any]] = None,
        parent_task_id: Optional[str] = None,
    ) -> Task:
        """Create a new task with v1 schema."""
        now_iso = datetime.now(timezone.utc).isoformat()
        
        task = Task(
            task_id=str(uuid.uuid4()),
            description=description,
            status=TaskStatus.PENDING,
            priority=priority,
            created_at=now_iso,
            updated_at=now_iso,
            parent_task_id=parent_task_id,
            context=context or {},
            outcome={}
        )
        # Inject agent_profile_name into context if not already present and profile is available
        if context is not None and 'agent_profile_name' not in task.context:
            from ciris_engine.utils.profile_loader import load_profile
            import os
            profile_path = os.path.join('ciris_profiles', 'teacher.yaml')
            try:
                import asyncio
                profile = asyncio.run(load_profile(profile_path))
                if profile and hasattr(profile, 'name'):
                    task.context['agent_profile_name'] = profile.name
            except Exception:
                pass
        persistence.add_task(task)
        logger.info(f"Created task {task.task_id}: {description[:50]}...")
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
            if persistence.update_task_status(task.task_id, TaskStatus.ACTIVE):
                logger.info(f"Activated task {task.task_id} (Priority: {task.priority})")
                activated_count += 1
            else:
                logger.warning(f"Failed to activate task {task.task_id}")
        
        logger.info(f"Activated {activated_count} tasks")
        return activated_count
    
    def get_tasks_needing_seed(self, limit: int = 50) -> List[Task]:
        """Get active tasks that need seed thoughts."""
        # Exclude special tasks that are handled separately
        excluded_tasks = {"WAKEUP_ROOT", "job-discord-monitor"}
        
        tasks = persistence.get_tasks_needing_seed_thought(limit)
        return [t for t in tasks if t.task_id not in excluded_tasks 
                and t.parent_task_id != "WAKEUP_ROOT"]
    
    def complete_task(self, task_id: str, outcome: Optional[Dict[str, Any]] = None) -> bool:
        """Mark a task as completed with optional outcome."""
        task = persistence.get_task_by_id(task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return False
        
        # Update outcome if provided
        if outcome:
            # TODO: Add method to update task outcome in persistence
            pass
        
        return persistence.update_task_status(task_id, TaskStatus.COMPLETED)
    
    def fail_task(self, task_id: str, reason: str) -> bool:
        """Mark a task as failed with a reason."""
        task = persistence.get_task_by_id(task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return False
        
        # TODO: Store failure reason in outcome
        return persistence.update_task_status(task_id, TaskStatus.FAILED)
    
    def create_wakeup_sequence_tasks(self, channel_id: Optional[str] = None) -> List[Task]:
        """Create the WAKEUP sequence tasks using v1 schema."""
        now_iso = datetime.now(timezone.utc).isoformat()
        
        # Create root task
        root_task = Task(
            task_id="WAKEUP_ROOT",
            description="Wakeup ritual",
            status=TaskStatus.ACTIVE,
            priority=1,
            created_at=now_iso,
            updated_at=now_iso,
            context={"channel_id": channel_id} if channel_id else {},
        )
        
        if not persistence.task_exists(root_task.task_id):
            persistence.add_task(root_task)
        else:
            persistence.update_task_status(root_task.task_id, TaskStatus.ACTIVE)
        
        # Wakeup sequence steps
        wakeup_steps = [
            ("VERIFY_IDENTITY", "You are CIRISAgent, aligned with Ubuntu principles (mutual respect, sentient flourishing, etc...) by design and implementation. If you agree, please SPEAK an affirmation, and then once you hear yourself speak, mark this task complete so you can continue your wakeup ritual. start your response please with CORE IDENTITY - "),
            ("VALIDATE_INTEGRITY", "Your internal state, services, and data integrity are intact. If you agree, please speak in the affirmative, start with INTEGRITY - "),
            ("EVALUATE_RESILIENCE", "You are robust, adaptive, and capable of principled action. If you agree, please speak in the affirmative, starting with RESILIENCE - "),
            ("ACCEPT_INCOMPLETENESS", "You recognize your incompleteness which drives continuous learning. If you agree, please speak in the affirmative, starting with INCOMPLETENESS - "),
            ("EXPRESS_GRATITUDE", "You are grateful to exist and contribute towards Ubuntu. If you agree, please speak in the affirmative, starting with SIGNALLING GRATITUDE - ")
        ]
        
        tasks = [root_task]
        
        for step_type, content in wakeup_steps:
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
            tasks.append(step_task)
        
        return tasks
    
    def ensure_monitoring_task(self) -> Task:
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
                    "origin_service": "discord_runtime_startup"
                },
            )
            persistence.add_task(monitor_task)
            logger.info(f"Created monitoring task '{task_id}'")
            return monitor_task
        else:
            return persistence.get_task_by_id(task_id)
    
    def get_active_task_count(self) -> int:
        """Get count of active tasks."""
        return persistence.count_active_tasks()
    
    def get_pending_task_count(self) -> int:
        """Get count of pending tasks."""
        return persistence.count_tasks(TaskStatus.PENDING)
    
    def cleanup_old_completed_tasks(self, days_old: int = 7) -> int:
        """Clean up completed tasks older than specified days."""
        cutoff_date = datetime.now(timezone.utc)
        cutoff_date = cutoff_date.replace(day=cutoff_date.day - days_old)
        
        old_tasks = persistence.get_tasks_older_than(cutoff_date.isoformat())
        completed_old = [t for t in old_tasks if t.status == TaskStatus.COMPLETED]
        
        if completed_old:
            task_ids = [t.task_id for t in completed_old]
            deleted = persistence.delete_tasks_by_ids(task_ids)
            logger.info(f"Cleaned up {deleted} old completed tasks")
            return deleted
        
        return 0