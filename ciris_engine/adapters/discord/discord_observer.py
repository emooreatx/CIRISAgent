import logging
import os
import asyncio
from typing import Callable, Awaitable, Dict, Any, Optional
from ciris_engine.schemas.graph_schemas_v1 import GraphScope

from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.schemas.service_actions_v1 import FetchMessagesAction
from ciris_engine.utils.constants import DEFAULT_WA
from ciris_engine.adapters.discord.discord_adapter import DiscordEventQueue
from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink

logger = logging.getLogger(__name__)


class DiscordObserver:
    """
    Observes IncomingMessage objects from a DiscordEventQueue, converts them into an OBSERVATION
    payload, and forwards it to the agent via `on_observe` for task creation.
    """

    def __init__(
        self,
        on_observe: Callable[[Dict[str, Any]], Awaitable[None]],
        message_queue: DiscordEventQueue,
        monitored_channel_id: Optional[str] = None,
        memory_service: Optional[Any] = None,
        agent_id: Optional[str] = None,
        multi_service_sink: Optional[MultiServiceActionSink] = None,
    ):
        self.on_observe = on_observe
        self.message_queue = message_queue
        self.memory_service = memory_service
        self.agent_id = agent_id
        self.multi_service_sink = multi_service_sink
        self._poll_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._history: list[IncomingMessage] = []

        env_id = os.getenv("DISCORD_CHANNEL_ID")
        if monitored_channel_id is None and env_id:
            monitored_channel_id = env_id.strip()
        self.monitored_channel_id: Optional[str] = monitored_channel_id

    async def start(self):
        if self.message_queue:
            self._poll_task = asyncio.create_task(self._poll_events())

    async def stop(self):
        if self._poll_task:
            self._stop_event.set()
            try:
                await asyncio.wait_for(self._poll_task, timeout=1.0)
            except asyncio.TimeoutError:
                logger.warning("DiscordObserver poll_task did not finish in time.")
                self._poll_task.cancel()
            except Exception as e:
                logger.error(f"Error stopping DiscordObserver poll_task: {e}")
            self._poll_task = None

    async def _poll_events(self) -> None:
        while not self._stop_event.is_set():
            try:
                msg = await asyncio.wait_for(self.message_queue.dequeue(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            await self.handle_incoming_message(msg)

    async def handle_incoming_message(self, msg: IncomingMessage) -> None:
        if not isinstance(msg, IncomingMessage):
            logger.warning("DiscordObserver received non-IncomingMessage")
            return
        if self.agent_id and msg.author_id == self.agent_id:
            logger.debug("Ignoring self message %s", msg.message_id)
            return
        # Only observe messages from the monitored channel
        if self.monitored_channel_id and msg.channel_id != self.monitored_channel_id:
            logger.debug("Ignoring message from channel %s (not monitored)", msg.channel_id)
            return
        # Store in history
        self._history.append(msg)
        # Passive observation routing
        await self._handle_passive_observation(msg)
        # Memory recall
        await self._recall_context(msg)

    async def _handle_passive_observation(self, msg: IncomingMessage) -> None:
        if not self.multi_service_sink:
            logger.warning("No multi_service_sink available for passive observation")
            return
        default_channel_id = os.getenv("DISCORD_CHANNEL_ID")
        deferral_channel_id = os.getenv("DISCORD_DEFERRAL_CHANNEL_ID")
        wa_discord_user = os.getenv("WA_DISCORD_USER", DEFAULT_WA)
        if msg.channel_id == default_channel_id and not self._is_agent_message(msg):
            await self._create_passive_observation_result(msg)
        elif msg.channel_id == deferral_channel_id and msg.author_name == wa_discord_user:
            await self._add_to_feedback_queue(msg)
        else:
            logger.debug("Ignoring message from channel %s, author %s", msg.channel_id, msg.author_name)

    def _is_agent_message(self, msg: IncomingMessage) -> bool:
        if self.agent_id and msg.author_id == self.agent_id:
            return True
        return msg.is_bot

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
                    handler_name="DiscordObserver",
                    channel_id=msg.channel_id,
                    content=f"[WA_FEEDBACK] {msg.content}",
                    metadata={
                        "message_type": "wa_feedback",
                        "original_message_id": msg.message_id,
                        "wa_user": msg.author_name,
                        "source": "discord_observer"
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
                GraphScope.IDENTITY,
                GraphScope.ENVIRONMENT,
                GraphScope.LOCAL,
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
