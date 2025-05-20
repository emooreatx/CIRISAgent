"""Service action for SPEAK."""

import logging

logger = logging.getLogger(__name__)

from typing import TYPE_CHECKING
from ..agent_core_schemas import Thought
from .helpers import create_follow_up_thought

if TYPE_CHECKING:
    from ...services.discord_service import DiscordService

async def handle_speak(
    thought: Thought, params: dict, discord_service: "DiscordService", **kwargs
) -> Thought:
    """Send a Discord message and return a follow-up Thought."""
    content = params["content"]
    target_channel = params.get("target_channel")
    await discord_service.send_output(target_channel, content)
    return create_follow_up_thought(thought)
