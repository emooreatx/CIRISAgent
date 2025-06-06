from datetime import datetime, timezone
import uuid
import logging
from typing import Optional, Dict, Any

from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, ThoughtType

logger = logging.getLogger(__name__)


def create_follow_up_thought(
    parent: Thought, 
    content: str = "", 
    thought_type: ThoughtType = ThoughtType.FOLLOW_UP
) -> Thought:
    """Return a new Thought linked to ``parent``.

    The original Thought instance is never mutated.
    ``source_task_id`` is inherited and ``parent_thought_id`` references the
    parent thought's ID to maintain lineage.
    """
    now = datetime.now(timezone.utc).isoformat()
    parent_round = parent.round_number if hasattr(parent, 'round_number') else 0
    from ciris_engine.schemas.context_schemas_v1 import ThoughtContext, SystemSnapshot

    if parent.context is not None:
        ctx = parent.context.copy() if isinstance(parent.context, dict) else parent.context.model_copy()
        # Ensure channel_id is propagated if present in parent context
        channel_id = None
        if hasattr(parent.context, 'get'):
            channel_id = parent.context.get('channel_id')
        elif hasattr(parent.context, 'channel_id'):
            channel_id = getattr(parent.context, 'channel_id', None)
        # Patch: propagate channel_id into system_snapshot if present
        if channel_id:
            if hasattr(ctx, 'system_snapshot') and hasattr(ctx.system_snapshot, 'channel_id'):
                ctx.system_snapshot.channel_id = channel_id
            elif hasattr(ctx, 'get') and 'system_snapshot' in ctx and hasattr(ctx['system_snapshot'], 'channel_id'):
                ctx['system_snapshot'].channel_id = channel_id
    else:
        ctx = ThoughtContext(system_snapshot=SystemSnapshot())

    follow_up = Thought(
        thought_id=str(uuid.uuid4()),
        source_task_id=parent.source_task_id,
        thought_type=thought_type,
        status=ThoughtStatus.PENDING,
        created_at=now,
        updated_at=now,
        round_number=parent_round,
        content=content,
        context=ctx,
        ponder_count=0,
        ponder_notes=None,
        parent_thought_id=parent.thought_id,
        final_action={},
    )
    return follow_up
