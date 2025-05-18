import logging
from typing import Callable, Awaitable, Dict, Any

from .base import Service

logger = logging.getLogger(__name__)


class DiscordObserver(Service):
    """Minimal observer that dispatches OBSERVE payloads from Discord events."""

    def __init__(self, on_observe: Callable[[Dict[str, Any]], Awaitable[None]]):
        super().__init__()
        self.on_observe = on_observe

    async def start(self):
        await super().start()

    async def stop(self):
        await super().stop()

    async def handle_event(self, user_nick: str, channel: str):
        payload = {"user_nick": user_nick, "channel": channel}
        if self.on_observe:
            await self.on_observe(payload)
        else:
            logger.debug("Observation: %s", payload)
