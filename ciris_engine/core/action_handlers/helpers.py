from datetime import datetime, timezone
import uuid

from ..agent_core_schemas import Thought, ThoughtStatus


def create_follow_up_thought(parent: Thought, content: str = "", thought_type: str = "follow_up") -> Thought:
    """Return a new Thought linked to ``parent``.

    The original Thought instance is never mutated.
    ``source_task_id`` is inherited and ``related_thought_id`` references the
    parent thought's ID to maintain lineage.
    """
    now = datetime.now(timezone.utc).isoformat()
    return Thought(
        thought_id=str(uuid.uuid4()),
        source_task_id=parent.source_task_id,
        thought_type=thought_type,
        status=ThoughtStatus.PENDING,
        created_at=now,
        updated_at=now,
        round_created=parent.round_created,
        content=content,
        related_thought_id=parent.thought_id,
        priority=parent.priority,
    )
