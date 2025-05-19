import logging
import os
from typing import Callable, Awaitable, Dict, Any, Iterable, Optional

from .base import Service

logger = logging.getLogger(__name__)


class DiscordObserver(Service):
    """
    Minimal observer that converts raw Discord events into an OBSERVATION
    payload and forwards it to the agent via `on_observe`.
    """

    def __init__(
        self,
        on_observe: Callable[[Dict[str, Any]], Awaitable[None]],
        allowed_channel_ids: Optional[Iterable[str]] = None,
    ):
        super().__init__()
        self.on_observe = on_observe

        # Allow channel-level filtering via env or constructor
        env_ids = os.getenv("ALLOWED_CHANNEL_IDS")
        if allowed_channel_ids is None and env_ids:
            allowed_channel_ids = [c.strip() for c in env_ids.split(",") if c.strip()]

        self.allowed_channel_ids: Optional[set[str]] = (
            set(allowed_channel_ids) if allowed_channel_ids else None
        )

    async def start(self):
        await super().start()

    async def stop(self):
        await super().stop()

    async def handle_event(
        self, user_nick: str, channel: str, message_content: str
    ) -> None:
        """
        Translate a Discord message into an OBSERVATION task.

        The agent should treat this purely as a piece of information it
        may or may not respond to, never as a command.
        """
        # Skip if channel filtering is enabled and this channel is not allowed
        if self.allowed_channel_ids and channel not in self.allowed_channel_ids:
            logger.debug("Ignoring message from disallowed channel: %s", channel)
            return

        payload: Dict[str, Any] = {
            "type": "OBSERVATION",
            "context": {
                "user_nick": user_nick,
                "channel": channel,
                "message_text": message_content,
            },
            "task_description": (
                f"As a result of your permanent job task, you observed user "
                f"@{user_nick} in channel #{channel} say: '{message_content}'. "
                "Use your decision-making algorithms to decide whether to respond, "
                "ignore, or take any other appropriate action."
            ),
        }

        if self.on_observe:
            await self.on_observe(payload)
