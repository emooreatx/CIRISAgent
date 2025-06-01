import logging
import os
import asyncio
from typing import Callable, Awaitable, Dict, Any, Optional
from ciris_engine.schemas.graph_schemas_v1 import GraphScope

from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.sinks import MultiServiceDeferralSink
from ciris_engine.adapters.discord.discord_adapter import DiscordEventQueue

logger = logging.getLogger(__name__)


class DiscordObserver:
    """
    Observes IncomingMessage objects from a DiscordEventQueue, converts them into an OBSERVATION
    payload, and forwards it to the agent via `on_observe` for task creation.
    """

    def __init__(
        self,
        on_observe: Callable[[Dict[str, Any]], Awaitable[None]], # This callback will create the Task
        message_queue: DiscordEventQueue, # Use DiscordEventQueue[IncomingMessage]
        monitored_channel_id: Optional[str] = None,
        deferral_sink: Optional[MultiServiceDeferralSink] = None,
        memory_service: Optional[Any] = None,
        agent_id: Optional[str] = None,
    ):
        self.on_observe = on_observe
        self.message_queue = message_queue # Store the DiscordEventQueue[IncomingMessage]
        self.deferral_sink = deferral_sink
        self.memory_service = memory_service
        self.agent_id = agent_id
        self._poll_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._history: list[IncomingMessage] = []

        env_id = os.getenv("DISCORD_CHANNEL_ID")
        if monitored_channel_id is None and env_id:
            monitored_channel_id = env_id.strip()

        self.monitored_channel_id: Optional[str] = monitored_channel_id

    async def start(self):
        if self.message_queue: # Check if the new message_queue is provided
            self._poll_task = asyncio.create_task(self._poll_events())

    async def stop(self):
        if self._poll_task:
            self._stop_event.set()
            try:
                await asyncio.wait_for(self._poll_task, timeout=1.0)
            except asyncio.TimeoutError:
                logger.warning("DiscordObserver poll_task did not finish in time.")
                self._poll_task.cancel() # Force cancel if it doesn't stop
            except Exception as e:
                logger.error(f"Error stopping DiscordObserver poll_task: {e}")
            self._poll_task = None

    async def _poll_events(self) -> None:
        while not self._stop_event.is_set():
            try:
                incoming_msg = await asyncio.wait_for(self.message_queue.dequeue(), timeout=0.1)
                if incoming_msg:
                    await self.handle_incoming_message(incoming_msg)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.exception(f"DiscordObserver: Error during event polling: {e}")
                await asyncio.sleep(1)

    async def handle_incoming_message(self, msg: IncomingMessage) -> None:
        if not isinstance(msg, IncomingMessage):
            logger.warning(f"DiscordObserver: Received non-IncomingMessage object: {type(msg)}. Skipping.")
            return
        if self.agent_id and msg.author_id == self.agent_id:
            logger.debug("Ignoring self message %s", msg.message_id)
            return
        if self.monitored_channel_id and msg.channel_id != self.monitored_channel_id:
            logger.debug(f"DiscordObserver: Ignoring message from unmonitored channel: {msg.channel_id} for message {msg.message_id}")
            return
        raw_msg = getattr(msg, "_raw_message", None)
        payload: Dict[str, Any] = {
            "type": "OBSERVATION",
            "message_id": msg.message_id,
            "content": msg.content,
            "context": {
                "origin_service": "discord",
                "author_id": msg.author_id,
                "author_name": msg.author_name,
                "channel_id": msg.channel_id,
            },
            "task_description": (
                f"Observed user @{msg.author_name} (ID: {msg.author_id}) in channel #{msg.channel_id} (Msg ID: {msg.message_id}) say: '{msg.content}'. "
                "Evaluate and decide on the appropriate course of action."
            ),
        }
        if self.on_observe:
            try:
                await self.on_observe(payload)
                logger.debug(f"DiscordObserver: Forwarded message {msg.message_id} to on_observe callback.")
            except Exception as e:
                logger.exception(f"DiscordObserver: Error calling on_observe for message {msg.message_id}: {e}")
        else:
            logger.warning(f"DiscordObserver: on_observe callback not set. Message {msg.message_id} not processed for task creation.")
        await self._recall_context(msg)

    async def _recall_context(self, msg: IncomingMessage) -> None:
        if not self.memory_service:
            return
        recall_ids = {f"channel/{msg.channel_id}"}
        for m in self._history[-10:]:
            if m.author_id:
                recall_ids.add(f"user/{m.author_id}")
        for rid in recall_ids:
            for scope in (
                GraphScope.IDENTITY,
                GraphScope.ENVIRONMENT,
                GraphScope.LOCAL,
            ):
                try:
                    await self.memory_service.recall(rid, scope)
                except Exception:
                    continue
