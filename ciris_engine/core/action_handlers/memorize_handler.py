"""Service action for MEMORIZE."""

import logging

logger = logging.getLogger(__name__)

from typing import TYPE_CHECKING
from ..agent_core_schemas import Thought
from .helpers import create_follow_up_thought

if TYPE_CHECKING:
    from ...services.discord_graph_memory import DiscordGraphMemory

async def handle_memorize(
    thought: Thought, params: dict, memory_service: "DiscordGraphMemory"
) -> Thought:
    """Write user metadata and return a follow-up Thought."""
    user_nick = params["user_nick"]
    channel = params.get("channel")
    metadata = params.get("metadata", {})
    await memory_service.memorize(user_nick, channel, metadata)
    return create_follow_up_thought(thought)
