import json
import logging
from typing import Any, Dict, Optional
from ciris_engine.ports import DeferralSink
from ciris_engine.adapters.discord.discord_adapter import DiscordAdapter

logger = logging.getLogger(__name__)

def _truncate_discord_message(message: str, limit: int = 1900) -> str:
    return message if len(message) <= limit else message[:limit-3] + "..."

class DiscordDeferralSink(DeferralSink):
    """Send deferral reports via Discord."""
    def __init__(self, adapter: DiscordAdapter, deferral_channel_id: Optional[str]):
        self.adapter = adapter
        self.client = adapter.client
        self.deferral_channel_id = int(deferral_channel_id) if deferral_channel_id else None

    async def start(self):
        pass

    async def stop(self):
        pass

    async def send_deferral(self, task_id: str, thought_id: str, reason: str, package: Dict[str, Any]) -> None:
        if not self.deferral_channel_id:
            logger.warning("DiscordDeferralSink: deferral channel not configured")
            return
        channel = self.client.get_channel(self.deferral_channel_id)
        if channel is None:
            channel = await self.client.fetch_channel(self.deferral_channel_id)
        if channel is None:
            logger.error("DiscordDeferralSink: cannot access deferral channel %s", self.deferral_channel_id)
            return
        if "metadata" in package and "user_nick" in package:
            report = (
                f"**Memory Deferral Report**\n"
                f"**Task ID:** `{task_id}`\n"
                f"**Deferred Thought ID:** `{thought_id}`\n"
                f"**User:** {package.get('user_nick')} Channel: {package.get('channel')}\n"
                f"**Reason:** {reason}\n"
                f"**Metadata:** ```json\n{json.dumps(package.get('metadata'), indent=2)}\n```"
            )
        else:
            report = (
                f"**Deferral Report**\n"
                f"**Task ID:** `{task_id}`\n"
                f"**Deferred Thought ID:** `{thought_id}`\n"
                f"**Reason:** {reason}\n"
                f"**Deferral Package:** ```json\n{json.dumps(package, indent=2)}\n```"
            )
        await channel.send(_truncate_discord_message(report))
