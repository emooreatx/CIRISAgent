import asyncio
from typing import Callable, Awaitable, Dict, Any, Optional
import os
import logging

from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.utils.constants import DEFAULT_WA
from .api_event_queue import APIEventQueue
from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink

logger = logging.getLogger(__name__)

class APIObserver:
    def __init__(
        self,
        on_observe: Callable[[Dict[str, Any]], Awaitable[None]],
        message_queue: APIEventQueue,
        memory_service: Optional[Any] = None,
        agent_id: Optional[str] = None,
        multi_service_sink: Optional[MultiServiceActionSink] = None,
    ):
        self.on_observe = on_observe
        self.message_queue = message_queue
        self.memory_service = memory_service
        self.agent_id = agent_id
        self.multi_service_sink = multi_service_sink
        self._running = False
        self._history: list[IncomingMessage] = []

    async def start(self):
        self._running = True
        asyncio.create_task(self._process_messages())

    async def stop(self):
        self._running = False

    async def _process_messages(self):
        while self._running:
            try:
                msg = await asyncio.wait_for(self.message_queue.dequeue(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            await self.handle_incoming_message(msg)

    async def handle_incoming_message(self, msg: IncomingMessage) -> None:
        if not isinstance(msg, IncomingMessage):
            logger.warning("APIObserver received non-IncomingMessage")
            return
        if self.agent_id and msg.author_id == self.agent_id:
            logger.debug("Ignoring self message %s", msg.message_id)
            return
        self._history.append(msg)
        await self._handle_passive_observation(msg)
        await self._recall_context(msg)

    async def _handle_passive_observation(self, msg: IncomingMessage) -> None:
        if not self.multi_service_sink:
            logger.warning("No multi_service_sink available for passive observation")
            return
        default_channel_id = os.getenv("API_CHANNEL_ID")
        deferral_channel_id = os.getenv("API_DEFERRAL_CHANNEL_ID")
        wa_api_user = os.getenv("WA_API_USER", DEFAULT_WA)
        if msg.channel_id == default_channel_id and not self._is_agent_message(msg):
            await self._create_passive_observation_result(msg)
        elif msg.channel_id == deferral_channel_id and msg.author_name == wa_api_user:
            await self._add_to_feedback_queue(msg)
        else:
            logger.debug("Ignoring message from channel %s, author %s", msg.channel_id, msg.author_name)

    def _is_agent_message(self, msg: IncomingMessage) -> bool:
        if self.agent_id and msg.author_id == self.agent_id:
            return True
        return getattr(msg, "is_bot", False)

    async def _create_passive_observation_result(self, msg: IncomingMessage) -> None:
        try:
            if self.on_observe:
                payload = {
                    "message": {
                        "message_id": msg.message_id,
                        "content": msg.content,
                        "author_id": msg.author_id,
                        "author_name": msg.author_name,
                        "channel_id": msg.channel_id,
                        "timestamp": getattr(msg, "timestamp", None),
                        "is_bot": getattr(msg, "is_bot", False),
                        "is_dm": getattr(msg, "is_dm", False),
                    },
                    "task_description": (
                        f"Observed user @{msg.author_name} (ID: {msg.author_id}) in channel #{msg.channel_id} (Msg ID: {msg.message_id}) say: '{msg.content}'. "
                        "Evaluate and decide on the appropriate course of action."
                    ),
                }
                await self.on_observe(payload)
                logger.info(f"Created passive observation for message {msg.message_id}")
            else:
                logger.warning("No observation callback available for passive observation")
        except Exception as e:
            logger.error(f"Error creating passive observation result for message {msg.message_id}: {e}")

    async def _add_to_feedback_queue(self, msg: IncomingMessage) -> None:
        try:
            if self.multi_service_sink:
                success = await self.multi_service_sink.send_message(
                    handler_name="APIObserver",
                    channel_id=msg.channel_id,
                    content=f"[WA_FEEDBACK] {msg.content}",
                    metadata={
                        "message_type": "wa_feedback",
                        "original_message_id": msg.message_id,
                        "wa_user": msg.author_name,
                        "source": "api_observer"
                    }
                )
                if success:
                    logger.info(f"Enqueued WA feedback message {msg.message_id} from {msg.author_name}")
                else:
                    logger.warning(f"Failed to enqueue WA feedback message {msg.message_id}")
            else:
                logger.warning("No multi_service_sink available for WA feedback routing")
        except Exception as e:
            logger.error(f"Error adding WA feedback message {msg.message_id} to queue: {e}")

    async def _recall_context(self, msg: IncomingMessage) -> None:
        if not self.memory_service:
            return
        recall_ids = {f"channel/{msg.channel_id}"}
        for m in self._history[-10:]:
            if m.author_id:
                recall_ids.add(f"user/{m.author_id}")
        for rid in recall_ids:
            for scope in (
                "IDENTITY",
                "ENVIRONMENT",
                "LOCAL",
            ):
                try:
                    await self.memory_service.recall(rid, scope)
                except Exception:
                    continue

    async def get_recent_messages(self, limit: int = 20) -> list[Dict[str, Any]]:
        msgs = self._history[-limit:]
        return [
            {
                "id": m.message_id,
                "content": m.content,
                "author_id": m.author_id,
                "timestamp": getattr(m, "timestamp", "n/a"),
            }
            for m in msgs
        ]
