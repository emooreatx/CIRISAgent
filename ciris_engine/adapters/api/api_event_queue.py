import asyncio
from typing import TypeVar, Generic

T = TypeVar('T')

class APIEventQueue(Generic[T]):
    """Simple async queue for API events."""
    def __init__(self, maxsize: int = 100):
        self._queue = asyncio.Queue(maxsize=maxsize)

    async def enqueue(self, event: T) -> None:
        await self._queue.put(event)

    def enqueue_nowait(self, event: T) -> None:
        self._queue.put_nowait(event)

    async def dequeue(self) -> T:
        return await self._queue.get()

    def empty(self) -> bool:
        return self._queue.empty()
