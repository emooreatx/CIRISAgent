from ..agent_core_schemas import Thought
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...services.discord_service import DiscordService

async def handle_speak(thought: Thought, params: dict, discord_service: "DiscordService"):
    content = params["content"]
    target_channel = params.get("target_channel")
    await discord_service.send_message(target_channel, content)
    thought.action_count += 1
    thought.history.append({"action": "speak", "content": content})
