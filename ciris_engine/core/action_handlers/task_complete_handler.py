"""Handler for TASK_COMPLETE."""

import logging

logger = logging.getLogger(__name__)

from ..agent_core_schemas import Thought

async def handle_task_complete(thought: Thought, params: dict, **kwargs) -> None:
    """Mark the originating thought as terminal."""
    thought.is_terminal = True
