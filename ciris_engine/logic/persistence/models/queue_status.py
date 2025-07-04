"""Queue status functions for centralized access to task and thought counts."""

from typing import Optional
from dataclasses import dataclass

from ciris_engine.schemas.runtime.enums import TaskStatus, ThoughtStatus
from .tasks import count_tasks
from .thoughts import count_thoughts
from ..analytics import count_thoughts_by_status


@dataclass
class QueueStatus:
    """Queue status with pending tasks and thoughts counts."""
    pending_tasks: int
    pending_thoughts: int
    processing_thoughts: int = 0
    total_tasks: int = 0
    total_thoughts: int = 0


def get_queue_status(db_path: Optional[str] = None) -> QueueStatus:
    """
    Get current queue status with task and thought counts.
    
    This is the centralized function for getting queue counts,
    used by both the system context builder and the agent processor.
    
    Args:
        db_path: Optional database path override
        
    Returns:
        QueueStatus object with counts
    """
    # Get task counts
    pending_tasks = count_tasks(TaskStatus.PENDING, db_path=db_path)
    total_tasks = count_tasks(db_path=db_path)
    
    # Get thought counts
    # Note: count_thoughts() already returns PENDING + PROCESSING count
    pending_thoughts = count_thoughts_by_status(ThoughtStatus.PENDING)
    processing_thoughts = count_thoughts_by_status(ThoughtStatus.PROCESSING)
    total_pending_and_processing = count_thoughts(db_path=db_path)
    
    # For total thoughts, we need all statuses
    total_thoughts = (
        pending_thoughts + 
        processing_thoughts + 
        count_thoughts_by_status(ThoughtStatus.COMPLETED) +
        count_thoughts_by_status(ThoughtStatus.FAILED)
    )
    
    return QueueStatus(
        pending_tasks=pending_tasks,
        pending_thoughts=pending_thoughts,
        processing_thoughts=processing_thoughts,
        total_tasks=total_tasks,
        total_thoughts=total_thoughts
    )