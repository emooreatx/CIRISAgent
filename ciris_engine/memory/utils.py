import logging
from typing import Any

from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus
from ..core import persistence
from .ciris_local_graph import CIRISLocalGraph, MemoryOpResult, MemoryOpStatus

logger = logging.getLogger(__name__)


def is_wa_feedback(thought: Thought) -> bool:
    """Check if thought represents WA feedback for identity/environment updates."""
    ctx = thought.processing_context or {}
    return (
        ctx.get("is_wa_feedback", False) and 
        ctx.get("feedback_target") in ["identity", "environment"]
    )


def process_feedback(thought: Thought, memory_service: CIRISLocalGraph) -> MemoryOpResult:
    """Process WA feedback for graph updates."""
    ctx = thought.processing_context
    target = ctx.get("feedback_target")
    
    if target == "identity":
        return memory_service.update_identity_graph(ctx.get("feedback_data"))
    elif target == "environment":
        return memory_service.update_environment_graph(ctx.get("feedback_data"))
    else:
        return MemoryOpResult(status=MemoryOpStatus.DENIED, reason="Invalid feedback target")
