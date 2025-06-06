
from datetime import datetime, timezone
from typing import Dict, Any
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
    thought: Any, dma_name: str, error: Exception, retry_limit: int
) -> None:
    """Escalate when a DMA repeatedly fails.

    Supports both ``Thought`` objects and ``ProcessingQueueItem``s. When a queue
    item is provided we update the persisted ``Thought`` directly via the
    persistence layer.
    """

    from ciris_engine import persistence
    from ciris_engine.processor.processing_queue import ProcessingQueueItem

    now = datetime.now(timezone.utc).isoformat()
    reason = f"DMA failed after {retry_limit} attempts: {error}"
    event = {
        "timestamp": now,
        "dma": dma_name,
        "reason": reason,
        "type": "dma_failure",
    }

    if isinstance(thought, ProcessingQueueItem):
        persistence.update_thought_status(
            thought_id=thought.thought_id,
            status=ThoughtStatus.DEFERRED,
            final_action={"error": reason},
        )
        return

    thought.status = ThoughtStatus.DEFERRED
    _append_escalation(thought, event)


def escalate_due_to_max_thought_rounds(thought: Thought, max_rounds: int) -> Thought:
    """Escalate when a thought exceeds the allowed action rounds per thought."""
    now = datetime.now(timezone.utc).isoformat()
    event = {
        "timestamp": now,
        "reason": f"Thought action count exceeded maximum rounds of {max_rounds}",
        "type": "max_thought_rounds",
    }
    return _append_escalation(thought, event)
