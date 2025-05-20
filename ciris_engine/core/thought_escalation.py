from datetime import datetime, timezone
from typing import Dict

from .agent_core_schemas import Thought

__all__ = [
    "escalate_due_to_action_limit",
    "escalate_due_to_sla",
    "escalate_due_to_guardrail",
    "escalate_due_to_failure",
]


def _append_escalation(thought: Thought, event: Dict[str, str]) -> Thought:
    """Append an escalation event to the thought."""
    thought.escalations.append(event)
    return thought


def escalate_due_to_action_limit(thought: Thought, reason: str) -> Thought:
    """Escalate when a thought exceeds its action limit."""
    now = datetime.now(timezone.utc).isoformat()
    event = {
        "timestamp": now,
        "reason": reason,
        "type": "action_limit",
    }
    return _append_escalation(thought, event)


def escalate_due_to_sla(thought: Thought, reason: str) -> Thought:
    """Escalate when a thought breaches its SLA."""
    now = datetime.now(timezone.utc).isoformat()
    event = {
        "timestamp": now,
        "reason": reason,
        "type": "sla_breach",
    }
    thought.is_terminal = True
    return _append_escalation(thought, event)


def escalate_due_to_guardrail(thought: Thought, reason: str) -> Thought:
    """Escalate when a guardrail violation occurs."""
    now = datetime.now(timezone.utc).isoformat()
    event = {
        "timestamp": now,
        "reason": reason,
        "type": "guardrail_violation",
    }
    thought.is_terminal = True
    return _append_escalation(thought, event)


def escalate_due_to_failure(thought: Thought, reason: str) -> Thought:
    """Escalate due to internal failure or deferral."""
    now = datetime.now(timezone.utc).isoformat()
    event = {
        "timestamp": now,
        "reason": reason,
        "type": "internal_failure",
    }
    thought.is_terminal = True
    return _append_escalation(thought, event)
