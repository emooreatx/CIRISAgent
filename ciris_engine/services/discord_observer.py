import logging
import os
from typing import Callable, Awaitable, Dict, Any, Iterable, Optional

from .base import Service

logger = logging.getLogger(__name__)


class DiscordObserver(Service):
    """Minimal observer that dispatches OBSERVE payloads from Discord events."""

    def __init__(
        self,
        on_observe: Callable[[Dict[str, Any]], Awaitable[None]],
        allowed_channel_ids: Optional[Iterable[str]] = None,
    ):
        super().__init__()
        self.on_observe = on_observe
        env_ids = os.getenv("ALLOWED_CHANNEL_IDS")
        if allowed_channel_ids is None and env_ids:
            allowed_channel_ids = [c.strip() for c in env_ids.split(",") if c.strip()]
        self.allowed_channel_ids = set(allowed_channel_ids) if allowed_channel_ids else None

    async def start(self):
        await super().start()

    async def stop(self):
        await super().stop()

    async def handle_event(self, user_nick: str, channel: str):
        if self.allowed_channel_ids is not None and channel not in self.allowed_channel_ids:
            logger.debug("DiscordObserver ignored event from channel %s", channel)
            return

        payload = {"user_nick": user_nick, "channel": channel}
        if self.on_observe:
            await self.on_observe(payload)
        else:
            logger.debug("Observation: %s", payload)
