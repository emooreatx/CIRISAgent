import asyncio
from typing import TypeVar, Generic
import logging

logger = logging.getLogger(__name__)

T_Event = TypeVar('T_Event')

class DiscordEventQueue(Generic[T_Event]):
    """Simple generic async queue for events/messages."""
    def __init__(self, maxsize: int = 100):
        self._queue: asyncio.Queue[T_Event] = asyncio.Queue(maxsize=maxsize)
    async def enqueue(self, event: T_Event) -> None:
        await self._queue.put(event)
    def enqueue_nowait(self, event: T_Event) -> None:
        self._queue.put_nowait(event)
    async def dequeue(self) -> T_Event:
        return await self._queue.get()
    def empty(self) -> bool:
        return self._queue.empty()
