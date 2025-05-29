import asyncio
from typing import TypeVar, Generic, Any # Dict is no longer needed directly for the class definition
import logging

logger = logging.getLogger(__name__)

# Define a generic type variable for the event/message type
T_Event = TypeVar('T_Event')

class DiscordEventQueue(Generic[T_Event]):
    """Simple generic async queue for events/messages."""

    def __init__(self, maxsize: int = 100):
        self._queue: asyncio.Queue[T_Event] = asyncio.Queue(maxsize=maxsize)

    async def enqueue(self, event: T_Event) -> None:
        await self._queue.put(event)

    def enqueue_nowait(self, event: T_Event) -> None:
        """Enqueue without awaiting; raises QueueFull if full."""
        self._queue.put_nowait(event)

    async def dequeue(self) -> T_Event:
        return await self._queue.get()

    def empty(self) -> bool:
        return self._queue.empty()

# This file has moved to ciris_engine/adapters/discord/discord_event_queue.py
