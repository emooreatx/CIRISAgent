import asyncio
import logging
from typing import Callable, Awaitable, Dict, Any, Optional

from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.sinks import MultiServiceDeferralSink
from .cli_event_queues import CLIEventQueue

logger = logging.getLogger(__name__)

class CLIObserver:
    """Observer that converts CLI input events into observation payloads."""

    def __init__(
        self,
        on_observe: Callable[[Dict[str, Any]], Awaitable[None]],
        message_queue: CLIEventQueue[IncomingMessage],
        deferral_sink: Optional[MultiServiceDeferralSink] = None,
    ):
        self.on_observe = on_observe
        self.message_queue = message_queue
        self.deferral_sink = deferral_sink
        self._poll_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._history: list[IncomingMessage] = []

    async def start(self):
        self._poll_task = asyncio.create_task(self._poll_events())

    async def stop(self):
        if self._poll_task:
            self._stop_event.set()
            await self._poll_task
            self._poll_task = None
            self._stop_event.clear()

    async def _poll_events(self):
        while not self._stop_event.is_set():
            try:
                msg = await asyncio.wait_for(self.message_queue.dequeue(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            await self.handle_incoming_message(msg)

    async def handle_incoming_message(self, msg: IncomingMessage) -> None:
        if not isinstance(msg, IncomingMessage):
            logger.warning("CLIObserver received non-IncomingMessage")
            return
        self._history.append(msg)
        payload: Dict[str, Any] = {
            "type": "OBSERVATION",
            "message_id": msg.message_id,
            "content": msg.content,
            "context": {
                "origin_service": "cli",
                "author_id": msg.author_id,
                "author_name": msg.author_name,
                "channel_id": msg.channel_id,
            },
            "task_description": f"Observed CLI user say: '{msg.content}'",
        }
        if self.on_observe:
            await self.on_observe(payload)

    async def get_recent_messages(self, limit: int = 20) -> list[Dict[str, Any]]:
        """Return recent CLI messages for active observation."""
        msgs = self._history[-limit:]
        return [
            {
                "id": m.message_id,
                "content": m.content,
                "author_id": m.author_id,
                "timestamp": "n/a",
            }
            for m in msgs
        ]
