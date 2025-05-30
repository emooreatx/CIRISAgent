import asyncio
import logging
from typing import Optional

from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.protocols.services import CommunicationService
from .cli_event_queues import CLIEventQueue

logger = logging.getLogger(__name__)


class CLIAdapter(CommunicationService):
    """Simple CLI adapter implementing CommunicationService."""

    def __init__(self, message_queue: CLIEventQueue[IncomingMessage], interactive: bool = True):
        self.message_queue = message_queue
        self.interactive = interactive
        self._input_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def start(self):
        if self.interactive and self._input_task is None:
            self._input_task = asyncio.create_task(self._input_loop())

    async def stop(self):
        if self._input_task:
            self._stop_event.set()
            await self._input_task
            self._input_task = None
            self._stop_event.clear()

    async def _input_loop(self):
        while not self._stop_event.is_set():
            line = await asyncio.to_thread(input, ">>> ")
            if not line:
                continue
            if line.lower() in {"exit", "quit", "bye"}:
                self._stop_event.set()
                break
            msg = IncomingMessage(
                message_id=f"cli_{asyncio.get_event_loop().time()}",
                content=line,
                author_id="local_user",
                author_name="User",
                channel_id="cli",
            )
            await self.message_queue.enqueue(msg)

    async def send_message(self, channel_id: str, content: str) -> bool:
        print(f"[CLI][{channel_id}] {content}")
        return True

    async def fetch_messages(self, channel_id: str, limit: int = 100):
        return []

    def get_capabilities(self) -> list[str]:
        return ["send_message"]
