import uuid
from datetime import datetime, timezone

from ciris_engine.schemas.agent_core_schemas_v1 import Thought, ThoughtStatus
from ciris_engine.processor.thought_escalation import (
    escalate_due_to_action_limit,
    escalate_due_to_sla,
    escalate_due_to_guardrail,
    escalate_due_to_depth_limit,
    escalate_due_to_ponder_limit,
)


def create_thought() -> Thought:
    now = datetime.now(timezone.utc).isoformat()
    return Thought(
        thought_id=str(uuid.uuid4()),
        source_task_id="task1",
        thought_type="seed",
        status=ThoughtStatus.PENDING,
        created_at=now,
        updated_at=now,
        round_created=0,
        content="test",
    )


def test_escalate_due_to_action_limit():
    thought = create_thought()
    escalate_due_to_action_limit(thought, "limit reached")
    assert len(thought.escalations) == 1
    event = thought.escalations[0]
    assert event["type"] == "action_limit"
    assert "limit reached" in event["reason"]
    assert thought.is_terminal is False


def test_escalate_due_to_sla():
    thought = create_thought()
    escalate_due_to_sla(thought, "timeout")
    assert len(thought.escalations) == 1
    event = thought.escalations[0]
    assert event["type"] == "sla_breach"
    assert "timeout" in event["reason"]
    assert thought.is_terminal is True


def test_escalate_due_to_guardrail():
    thought = create_thought()
    escalate_due_to_guardrail(thought, "guardrail breached")
    assert len(thought.escalations) == 1
    event = thought.escalations[0]
    assert event["type"] == "guardrail_violation"
    assert "guardrail breached" in event["reason"]
    assert thought.is_terminal is True


def test_escalate_due_to_depth_limit():
    thought = create_thought()
    escalate_due_to_depth_limit(thought, 7)
    assert len(thought.escalations) == 1
    event = thought.escalations[0]
    assert event["type"] == "depth_limit"
    assert "7" in event["reason"]
    assert thought.is_terminal is True


def test_escalate_due_to_ponder_limit():
    thought = create_thought()
    escalate_due_to_ponder_limit(thought, 7)
    assert len(thought.escalations) == 1
    event = thought.escalations[0]
    assert event["type"] == "ponder_limit"
    assert "7" in event["reason"]
    assert thought.is_terminal is True
