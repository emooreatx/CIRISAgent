import pytest
from ciris_engine.action_handlers.helpers import create_follow_up_thought
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus


def make_parent():
    return Thought(
        thought_id=ThoughtStatus.PENDING,
        source_task_id=ThoughtStatus.PENDING,
        thought_type=ThoughtStatus.PENDING,
        status=ThoughtStatus.PENDING,
        created_at=ThoughtStatus.PENDING,
        updated_at=ThoughtStatus.PENDING,
        round_number=ThoughtStatus.PENDING,
        content=ThoughtStatus.PENDING,
        context={"channel_id": "chan", "foo": "bar"},
        ponder_count=ThoughtStatus.PENDING,
        ponder_notes=None,
        parent_thought_id=None,
        final_action={},
    )


def test_follow_up_copies_context():
    parent = make_parent()
    child = create_follow_up_thought(parent, content=ThoughtStatus.PENDING)
    assert child.parent_thought_id == parent.thought_id
    assert child.context.get("channel_id") == "chan"
    assert child.context.get("foo") == "bar"
