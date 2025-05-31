import asyncio
from typing import Callable, Awaitable, Dict, Any, Optional

from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from .api_event_queue import APIEventQueue

class APIObserver:
    def __init__(self, on_observe: Callable[[Dict[str, Any]], Awaitable[None]], message_queue: APIEventQueue):
        self.on_observe = on_observe
        self.message_queue = message_queue
        self._running = False

    async def start(self):
        self._running = True
        asyncio.create_task(self._process_messages())

    async def stop(self):
        self._running = False

    async def _process_messages(self):
        while self._running:
            try:
                msg = await asyncio.wait_for(self.message_queue.dequeue(), timeout=0.1)
                await self._handle_message(msg)
            except asyncio.TimeoutError:
                continue

    async def _handle_message(self, msg: IncomingMessage):
        payload = {
            "type": "OBSERVATION",
            "message_id": msg.message_id,
            "content": msg.content,
            "context": {
                "origin_service": "api",
                "author_id": msg.author_id,
                "author_name": msg.author_name,
                "channel_id": msg.channel_id,
            },
            "task_description": f"API request: {msg.content[:100]}...",
        }
        await self.on_observe(payload)
