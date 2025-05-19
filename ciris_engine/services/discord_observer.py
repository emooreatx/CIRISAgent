import logging
import os
import asyncio
from typing import Callable, Awaitable, Dict, Any, Optional

from .base import Service
from .discord_event_queue import DiscordEventQueue

logger = logging.getLogger(__name__)


class DiscordObserver(Service):
    """
    Minimal observer that converts raw Discord events into an OBSERVATION
    payload and forwards it to the agent via `on_observe`.
    """

    def __init__(
        self,
        on_observe: Callable[[Dict[str, Any]], Awaitable[None]],
        monitored_channel_id: Optional[str] = None,
        event_queue: Optional[DiscordEventQueue] = None,
    ):
        super().__init__()
        self.on_observe = on_observe
        self.event_queue = event_queue
        self._poll_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

        env_id = os.getenv("DISCORD_CHANNEL_ID")
        if monitored_channel_id is None and env_id:
            monitored_channel_id = env_id.strip()

        self.monitored_channel_id: Optional[str] = monitored_channel_id

    async def start(self):
        await super().start()
        if self.event_queue:
            self._poll_task = asyncio.create_task(self._poll_events())

    async def stop(self):
        if self._poll_task:
            self._stop_event.set()
            await self._poll_task
            self._poll_task = None
        await super().stop()

    async def _poll_events(self) -> None:
        while not self._stop_event.is_set():
            try:
                event = await asyncio.wait_for(self.event_queue.dequeue(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            except Exception:
                continue

            await self.handle_event(
                event.get("user_nick", ""),
                event.get("channel", ""),
                event.get("message_content", ""),
            )

    async def handle_event(
        self, user_nick: str, channel: str, message_content: str
    ) -> None:
        """
        Translate a Discord message into an OBSERVATION task.

        The agent should treat this purely as a piece of information it
        may or may not respond to, never as a command.
        """
        # Skip if a specific channel is configured and this is not it
        if self.monitored_channel_id and channel != self.monitored_channel_id:
            logger.debug("Ignoring message from unmonitored channel: %s", channel)
            return

        payload: Dict[str, Any] = {
            "type": "OBSERVATION",
            "context": {
                "user_nick": user_nick,
                "channel": channel,
                "message_text": message_content,
            },
            "task_description": (
                f"As a result of your permanent job task, you observed user @{user_nick} in channel #{channel} say: '{message_content}'. "
                "Use your decision-making algorithms to decide whether to respond, ignore, or take any other appropriate action."
            ),
        }

        if self.on_observe:
            await self.on_observe(payload)
