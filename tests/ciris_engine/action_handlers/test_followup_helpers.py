import pytest
from datetime import datetime, timezone
from ciris_engine.action_handlers.helpers import create_follow_up_thought
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, ThoughtType


def make_parent():
    now = datetime.now(timezone.utc)
    # Set channel_id and foo in context for propagation
    context = {"channel_id": "chan", "foo": "bar"}
    return Thought(
        thought_id="parent",
        source_task_id="task1",
        thought_type=ThoughtType.STANDARD,
        status=ThoughtStatus.PENDING,
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
        round_number=0,
        content="parent content",
        context=context,
        thought_depth=0,
        parent_thought_id=None,
        final_action={},
    )


def test_follow_up_copies_context():
    parent = make_parent()
    child = create_follow_up_thought(parent, content=ThoughtStatus.PENDING)
    assert child.parent_thought_id == parent.thought_id
    assert child.context.get("channel_id") == "chan"
    assert child.context.get("foo") == "bar"
