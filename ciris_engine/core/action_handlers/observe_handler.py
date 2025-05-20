"""Service action for OBSERVE."""

from ..agent_core_schemas import Thought
from .helpers import create_follow_up_thought

async def handle_observe(thought: Thought, params: dict, observer_service) -> Thought:
    """Perform observation and return a follow-up Thought."""
    await observer_service.observe(params)
    return create_follow_up_thought(thought)
