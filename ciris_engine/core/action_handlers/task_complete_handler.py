"""Handler for TASK_COMPLETE."""

from ..agent_core_schemas import Thought

async def handle_task_complete(thought: Thought, params: dict) -> None:
    """Mark the originating thought as terminal."""
    thought.is_terminal = True
