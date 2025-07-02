"""Common test helpers for CIRIS tests."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from ciris_engine.schemas.runtime.models import Task, Thought, TaskContext, ThoughtContext
from ciris_engine.schemas.runtime.enums import TaskStatus, ThoughtStatus, ThoughtType
from ciris_engine.logic import persistence


def create_test_task_with_persistence(
    task_id: Optional[str] = None,
    channel_id: str = "test_channel",
    description: str = "Test task"
) -> Task:
    """Create a test task and persist it to the database."""
    if task_id is None:
        task_id = f"test_task_{uuid.uuid4().hex[:8]}"
    
    task = Task(
        task_id=task_id,
        channel_id=channel_id,
        description=description,
        status=TaskStatus.PENDING,
        priority=5,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        context=TaskContext(
            channel_id=channel_id,
            user_id="test_user",
            correlation_id=f"test_correlation_{uuid.uuid4().hex[:8]}"
        )
    )
    
    # Persist the task to the database
    persistence.add_task(task)
    return task


def create_test_thought_with_persistence(
    thought_id: Optional[str] = None,
    task_id: Optional[str] = None,
    content: str = "Test thought content",
    status: ThoughtStatus = ThoughtStatus.PROCESSING,
    thought_type: ThoughtType = ThoughtType.STANDARD
) -> Thought:
    """Create a test thought with a persisted parent task."""
    # First ensure we have a parent task
    if task_id is None:
        task = create_test_task_with_persistence()
        task_id = task.task_id
    else:
        # Check if task exists, create if not
        existing_task = persistence.get_task_by_id(task_id)
        if not existing_task:
            create_test_task_with_persistence(task_id=task_id)
    
    if thought_id is None:
        thought_id = f"test_thought_{uuid.uuid4().hex[:8]}"
    
    thought = Thought(
        thought_id=thought_id,
        source_task_id=task_id,
        content=content,
        status=status,
        thought_type=thought_type,
        thought_depth=1,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        round_number=1,
        context=ThoughtContext(
            task_id=task_id,
            round_number=1,
            depth=1,
            correlation_id=f"test_correlation_{uuid.uuid4().hex[:8]}"
        )
    )
    
    # Persist the thought to the database
    persistence.add_thought(thought)
    return thought