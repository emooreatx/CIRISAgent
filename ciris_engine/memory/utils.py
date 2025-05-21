import logging
from typing import Any, Dict
try:
    import bleach
    def _clean(text: str) -> str:
        return bleach.clean(text)
except Exception:  # noqa: BLE001
    import html
    def _clean(text: str) -> str:
        return html.escape(text)

from ..core.agent_core_schemas import Thought
from ..core.foundational_schemas import ThoughtStatus
from ..core import persistence

logger = logging.getLogger(__name__)

class MemoryWriteKey:
    CHANNEL_PREFIX = "channel/"


def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize a dictionary's string values using bleach."""
    sanitized: Dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, str):
            sanitized[k] = _clean(v)
        else:
            sanitized[k] = v
    return sanitized


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
