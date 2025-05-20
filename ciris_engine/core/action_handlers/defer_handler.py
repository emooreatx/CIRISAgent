"""Service action for DEFER."""

import logging

logger = logging.getLogger(__name__)

from ..agent_core_schemas import Thought
from .helpers import create_follow_up_thought

async def handle_defer(thought: Thought, params: dict, **kwargs) -> Thought:
    """Mark the thought deferred and return a follow-up Thought."""
    reason = params.get("reason")
    thought.is_terminal = True
    return create_follow_up_thought(thought, content=str(reason))
