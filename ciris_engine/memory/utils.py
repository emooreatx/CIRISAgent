import logging
from typing import Any

from ..core.agent_core_schemas import Thought
from ..core.foundational_schemas import ThoughtStatus
from ..core import persistence

logger = logging.getLogger(__name__)

class MemoryWriteKey:
    CHANNEL_PREFIX = "channel/"


def classify_target(mem_write: "MemoryWrite") -> str:
    """Return 'CHANNEL' if the key path targets a channel node else 'USER'."""
    key = mem_write.key_path
    return "CHANNEL" if key.startswith(MemoryWriteKey.CHANNEL_PREFIX) else "USER"


def is_wa_correction(thought: Thought) -> bool:
    """Return True if the thought represents a WA correction for a deferred write."""
    ctx = thought.processing_context or {}
    if not ctx.get("is_wa_correction"):
        return False
    corrected_id = ctx.get("corrected_thought_id")
    if not corrected_id:
        return False
    parent = persistence.get_thought_by_id(corrected_id)
    return parent is not None and parent.status == ThoughtStatus.DEFERRED
