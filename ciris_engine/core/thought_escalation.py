from datetime import datetime, timezone
from typing import Dict
import logging

logger = logging.getLogger(__name__)

from .agent_core_schemas import Thought
from .foundational_schemas import ThoughtStatus

__all__ = [
    "escalate_due_to_action_limit",
    "escalate_due_to_sla",
    "escalate_due_to_guardrail",
    "escalate_due_to_failure",
    "escalate_dma_failure",
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


def escalate_dma_failure(
    thought: Thought, dma_name: str, error: Exception, retry_limit: int
) -> Thought:
    """Escalate when a DMA repeatedly fails."""
    now = datetime.now(timezone.utc).isoformat()
    event = {
        "timestamp": now,
        "dma": dma_name,
        "reason": f"DMA failed after {retry_limit} attempts: {error}",
        "type": "dma_failure",
    }
    thought.status = ThoughtStatus.DEFERRED
    return _append_escalation(thought, event)
