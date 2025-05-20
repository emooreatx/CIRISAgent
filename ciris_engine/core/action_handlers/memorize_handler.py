from ..agent_core_schemas import Thought
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...services.discord_graph_memory import DiscordGraphMemory

async def handle_memorize(thought: Thought, params: dict, memory_service: "DiscordGraphMemory"):
    user_nick = params["user_nick"]
    channel = params.get("channel")
    metadata = params.get("metadata", {})
    await memory_service.memorize(user_nick, channel, metadata)
    thought.action_count += 1
    thought.history.append({"action": "memorize", "user_nick": user_nick})
