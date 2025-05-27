from datetime import datetime, timezone
import uuid
import logging
from typing import Optional

# Updated imports for v1 schemas
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus

logger = logging.getLogger(__name__)


def create_follow_up_thought(
    parent: Thought, 
    content: str = "", 
    thought_type: str = "follow_up",
    priority_offset: Optional[int] = None
) -> Thought:
    """Return a new Thought linked to ``parent``.

    The original Thought instance is never mutated.
    ``source_task_id`` is inherited and ``parent_thought_id`` references the
    parent thought's ID to maintain lineage.
    Priority can be adjusted using priority_offset.
    """
    now = datetime.now(timezone.utc).isoformat()
    
    # v1 schema doesn't have priority field for thoughts
    # If priority is needed, it could be stored in the context
    priority = 0
    if hasattr(parent, 'priority'):
        priority = parent.priority
    
    if priority_offset is not None:
        priority += priority_offset
        # Ensure priority doesn't go below a reasonable minimum (e.g., 0)
        priority = max(0, priority)
    
    # Get parent's round number (v1 uses single round_number field)
    parent_round = parent.round_number if hasattr(parent, 'round_number') else 0

    # Create follow-up thought with v1 schema
    follow_up = Thought(
        thought_id=str(uuid.uuid4()),
        source_task_id=parent.source_task_id,
        thought_type=thought_type,
        status=ThoughtStatus.PENDING,
        created_at=now,
        updated_at=now,
        round_number=parent_round,
        content=content,
        parent_thought_id=parent.thought_id,
        context={},  # v1 uses 'context'
        ponder_count=0,
        ponder_notes=None,
        final_action={},
    )
    
    # If priority tracking is needed, store it in context
    if priority != 0:
        follow_up.context["priority"] = priority
    
    return follow_up