import asyncio
from typing import Dict, Any

class DiscordEventQueue:
    """Simple async queue for Discord events."""

    def __init__(self, maxsize: int = 100):
        self._queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=maxsize)

    async def enqueue(self, event: Dict[str, Any]) -> None:
        await self._queue.put(event)

    def enqueue_nowait(self, event: Dict[str, Any]) -> None:
        """Enqueue without awaiting; raises QueueFull if full."""
        self._queue.put_nowait(event)

    async def dequeue(self) -> Dict[str, Any]:
        return await self._queue.get()

    def empty(self) -> bool:
        return self._queue.empty()

