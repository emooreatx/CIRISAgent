"""Service action for DEFER."""

from ..agent_core_schemas import Thought
from .helpers import create_follow_up_thought

async def handle_defer(thought: Thought, params: dict) -> Thought:
    """Mark the thought deferred and return a follow-up Thought."""
    reason = params.get("reason")
    thought.is_terminal = True
    return create_follow_up_thought(thought, content=str(reason))
