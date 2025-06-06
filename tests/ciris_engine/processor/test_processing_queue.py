import pytest
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, ThoughtType


def make_thought():
    return Thought(
        thought_id="th1",
        source_task_id="t1",
        thought_type=ThoughtType.STANDARD,
        status=ThoughtStatus.PENDING,
        created_at="now",
        updated_at="now",
        round_number=1,
        content="hello",
        context={"foo": "bar"},
        ponder_count=0,
        ponder_notes=None,
        parent_thought_id=None,
        final_action={},
    )


def test_from_thought_with_overrides():
    t = make_thought()
    item = ProcessingQueueItem.from_thought(
        t,
        raw_input="raw",
        initial_ctx={"x": 1},
        queue_item_content="override",
    )
    assert item.thought_id == t.thought_id
    assert item.raw_input_string == "raw"
    assert item.initial_context == {"x": 1}
    assert item.content.text == "override"
    assert item.ponder_notes is None


def test_from_thought_defaults():
    t = make_thought()
    item = ProcessingQueueItem.from_thought(t)
    assert item.raw_input_string == str(t.content)
    assert item.initial_context == t.context
    assert item.content.text == t.content
