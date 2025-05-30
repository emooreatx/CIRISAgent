import asyncio
import logging
from typing import Any, TypeVar, Generic

logger = logging.getLogger(__name__)

T = TypeVar('T')

class CLIEventQueue(Generic[T]):
    """Generic async queue for CLI events."""
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

# Aliases for specific event types
CLIPassiveObserveQueue = CLIEventQueue
CLIActiveObserveQueue = CLIEventQueue
CLIFeedbackQueue = CLIEventQueue
