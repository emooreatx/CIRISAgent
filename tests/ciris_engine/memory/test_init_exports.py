import pytest
from ciris_engine.memory import classify_target, is_wa_feedback
from ciris_engine.memory.memory_handler import MemoryWrite
from ciris_engine.schemas.agent_core_schemas_v1 import Thought


def test_classify_target_channel_and_user():
    mw_channel = MemoryWrite(key_path="channel/#general/topic", user_nick="alice", value="foo")
    mw_user = MemoryWrite(key_path="user/alice/bio", user_nick="alice", value="bar")
    assert classify_target(mw_channel) == "CHANNEL"
    assert classify_target(mw_user) == "USER"

def test_is_wa_feedback_true_and_false():
    t_wa = Thought(
        thought_id="th1",
        source_task_id="t1",
        thought_type="test",
        status="pending",
        created_at="now",
        updated_at="now",
        round_number=1,
        content="test",
        context={"is_wa_feedback": True, "feedback_target": "identity"},
        ponder_count=0,
        ponder_notes=None,
        parent_thought_id=None,
        final_action={}
    )
    t_not_wa = Thought(
        thought_id="th2",
        source_task_id="t1",
        thought_type="test",
        status="pending",
        created_at="now",
        updated_at="now",
        round_number=1,
        content="test",
        context={},
        ponder_count=0,
        ponder_notes=None,
        parent_thought_id=None,
        final_action={}
    )
    assert is_wa_feedback(t_wa) is True
    assert is_wa_feedback(t_not_wa) is False
