# This file was moved from core/thought_escalation.py to core/processor/thought_escalation.py for better modularity and alignment with processing logic.
# See main_processor.py and thought_manager.py for usage.

from datetime import datetime, timezone
from typing import Dict
import logging

logger = logging.getLogger(__name__)

from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus

__all__ = [
    "escalate_due_to_action_limit",
    "escalate_due_to_sla",
    "escalate_due_to_guardrail",
    "escalate_due_to_failure",
    "escalate_dma_failure",
    "escalate_due_to_max_thought_rounds",
]


def _append_escalation(thought: Thought, event: Dict[str, str]) -> Thought:
    """Append an escalation event to the thought (no-op for v1 schema)."""
    # Escalation events are not tracked in v1 schema.
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
    return _append_escalation(thought, event)


def escalate_due_to_guardrail(thought: Thought, reason: str) -> Thought:
    """Escalate when a guardrail violation occurs."""
    now = datetime.now(timezone.utc).isoformat()
    event = {
        "timestamp": now,
        "reason": reason,
        "type": "guardrail_violation",
    }
    return _append_escalation(thought, event)


def escalate_due_to_failure(thought: Thought, reason: str) -> Thought:
    """Escalate due to internal failure or deferral."""
    now = datetime.now(timezone.utc).isoformat()
    event = {
        "timestamp": now,
        "reason": reason,
        "type": "internal_failure",
    }
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


def escalate_due_to_max_thought_rounds(thought: Thought, max_rounds: int) -> Thought:
    """Escalate when a thought exceeds the allowed action rounds per thought."""
    now = datetime.now(timezone.utc).isoformat()
    event = {
        "timestamp": now,
        "reason": f"Thought action count exceeded maximum rounds of {max_rounds}",
        "type": "max_thought_rounds",
    }
    return _append_escalation(thought, event)
