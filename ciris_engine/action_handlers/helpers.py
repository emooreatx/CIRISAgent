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
    thought_type: str = "follow_up"
) -> Thought:
    """Return a new Thought linked to ``parent``.

    The original Thought instance is never mutated.
    ``source_task_id`` is inherited and ``parent_thought_id`` references the
    parent thought's ID to maintain lineage.
    """
    now = datetime.now(timezone.utc).isoformat()
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
    return follow_up