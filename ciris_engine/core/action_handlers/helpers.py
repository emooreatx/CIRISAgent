from datetime import datetime, timezone
import uuid
import logging

logger = logging.getLogger(__name__)

from ..agent_core_schemas import Thought, ThoughtStatus
from typing import Optional # Added Optional for priority_offset


def create_follow_up_thought(
    parent: Thought, 
    content: str = "", 
    thought_type: str = "follow_up",
    priority_offset: Optional[int] = None
) -> Thought:
    """Return a new Thought linked to ``parent``.

    The original Thought instance is never mutated.
    ``source_task_id`` is inherited and ``related_thought_id`` references the
    parent thought's ID to maintain lineage.
    Priority can be adjusted using priority_offset.
    """
    now = datetime.now(timezone.utc).isoformat()
    
    new_priority = parent.priority
    if priority_offset is not None:
        new_priority += priority_offset
        # Ensure priority doesn't go below a reasonable minimum (e.g., 0 or 1)
        # or above a maximum if defined. For now, just simple addition.
        # Consider clamping if priorities have strict bounds.
        new_priority = max(0, new_priority) # Example: ensure non-negative

    return Thought(
        thought_id=str(uuid.uuid4()),
        source_task_id=parent.source_task_id,
        thought_type=thought_type,
        status=ThoughtStatus.PENDING,
        created_at=now,
        updated_at=now,
        round_created=parent.round_created, # Should this be current round? Or parent's round?
                                           # For now, keeping parent.round_created as it was.
                                           # If it's for the *next* round, it should be incremented.
        content=content,
        related_thought_id=parent.thought_id,
        priority=new_priority, # Use adjusted priority
    )
