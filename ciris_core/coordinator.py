"""Minimal workflow coordinator.

This coordinator is intentionally small for pre-alpha refactoring work. It
receives a :class:`Thought` and returns the recommended
:class:`HandlerActionType`. Real DMA logic will be integrated later.
"""

from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType


class Coordinator:
    """Simplified coordinator that decides on a final action."""

    async def process_thought(self, thought: Thought) -> HandlerActionType:
        """Return a basic action recommendation for the given thought."""
        if thought.thought_type == "seed":
            return HandlerActionType.SPEAK
        return HandlerActionType.PONDER
