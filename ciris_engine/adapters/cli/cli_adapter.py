import asyncio
import logging
from typing import Optional

from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.protocols.services import CommunicationService

logger = logging.getLogger(__name__)


class CLIAdapter(CommunicationService):
    """Simple CLI adapter implementing CommunicationService."""

    def __init__(self, interactive: bool = True):
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
            # CLI adapter in MultiServiceSink architecture just logs input
            # Message handling is done by observers/processors
            logger.info(f"CLI input received: {line}")

    async def send_message(self, channel_id: str, content: str) -> bool:
        print(f"[CLI][{channel_id}] {content}")
        return True

    async def fetch_messages(self, channel_id: str, limit: int = 100):
        # CLI adapter does not maintain history; return empty list
        return []

    def get_capabilities(self) -> list[str]:
        # Support both sending and fetching messages so the service
        # can satisfy communication requests via the registry
        return ["send_message", "fetch_messages"]
