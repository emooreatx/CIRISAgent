import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

class CLIPassiveObserveQueue:
    """Async queue for passive observe events (e.g., stdin, file, etc)."""
    def __init__(self, maxsize: int = 100):
        self._queue = asyncio.Queue(maxsize=maxsize)
    async def enqueue(self, event: Any) -> None:
        await self._queue.put(event)
    def enqueue_nowait(self, event: Any) -> None:
        self._queue.put_nowait(event)
    async def dequeue(self) -> Any:
        return await self._queue.get()
    def empty(self) -> bool:
        return self._queue.empty()

class CLIActiveObserveQueue:
    """Async queue for active observe events (e.g., explicit user input)."""
    def __init__(self, maxsize: int = 100):
        self._queue = asyncio.Queue(maxsize=maxsize)
    async def enqueue(self, event: Any) -> None:
        await self._queue.put(event)
    def enqueue_nowait(self, event: Any) -> None:
        self._queue.put_nowait(event)
    async def dequeue(self) -> Any:
        return await self._queue.get()
    def empty(self) -> bool:
        return self._queue.empty()

class CLIFeedbackQueue:
    """Async queue for feedback events (e.g., WA, user feedback)."""
    def __init__(self, maxsize: int = 100):
        self._queue = asyncio.Queue(maxsize=maxsize)
    async def enqueue(self, event: Any) -> None:
        await self._queue.put(event)
    def enqueue_nowait(self, event: Any) -> None:
        self._queue.put_nowait(event)
    async def dequeue(self) -> Any:
        return await self._queue.get()
    def empty(self) -> bool:
        return self._queue.empty()
