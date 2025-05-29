import pytest
from ciris_engine.action_handlers.helpers import create_follow_up_thought
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus


def make_parent():
    return Thought(
        thought_id="p1",
        source_task_id="task1",
        thought_type="test",
        status=ThoughtStatus.PENDING,
        created_at="now",
        updated_at="now",
        round_number=1,
        content="parent",
        context={"channel_id": "chan", "foo": "bar"},
        ponder_count=0,
        ponder_notes=None,
        parent_thought_id=None,
        final_action={},
    )


def test_follow_up_copies_context():
    parent = make_parent()
    child = create_follow_up_thought(parent, content="child")
    assert child.parent_thought_id == parent.thought_id
    assert child.context.get("channel_id") == "chan"
    assert child.context.get("foo") == "bar"
