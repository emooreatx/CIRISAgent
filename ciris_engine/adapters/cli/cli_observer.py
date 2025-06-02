import asyncio
import logging
import os
from typing import Callable, Awaitable, Dict, Any, Optional
from ciris_engine.schemas.graph_schemas_v1 import GraphScope

from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.schemas.service_actions_v1 import FetchMessagesAction
from ciris_engine.utils.constants import DEFAULT_WA
from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink


logger = logging.getLogger(__name__)

class CLIObserver:
    """Observer that converts CLI input events into observation payloads."""

    def __init__(
        self,
        on_observe: Callable[[Dict[str, Any]], Awaitable[None]],
        memory_service: Optional[Any] = None,
        agent_id: Optional[str] = None,
        multi_service_sink: Optional[MultiServiceActionSink] = None,
        *,
        interactive: bool = True,
    ):
        self.on_observe = on_observe
        self.memory_service = memory_service
        self.agent_id = agent_id
        self.multi_service_sink = multi_service_sink
        self.interactive = interactive
        self._input_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._history: list[IncomingMessage] = []

    async def start(self):
        """Start the observer and optional input loop."""
        logger.info("CLIObserver started")
        if self.interactive and self._input_task is None:
            self._input_task = asyncio.create_task(self._input_loop())

    async def stop(self):
        """Stop the observer and background input loop."""
        if self._input_task:
            self._stop_event.set()
            await self._input_task
            self._input_task = None
            self._stop_event.clear()
        logger.info("CLIObserver stopped")

    async def _input_loop(self) -> None:
        """Read lines from stdin and handle them as messages."""
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
            await self.handle_incoming_message(msg)

    async def handle_incoming_message(self, msg: IncomingMessage) -> None:
        if not isinstance(msg, IncomingMessage):
            logger.warning("CLIObserver received non-IncomingMessage")
            return
        if self.agent_id and msg.author_id == self.agent_id:
            logger.debug("Ignoring self message %s", msg.message_id)
            return
        
        # Store in history
        self._history.append(msg)
        
        # Handle passive observation: route incoming messages based on channel and author
        await self._handle_passive_observation(msg)

    async def _handle_passive_observation(self, msg: IncomingMessage) -> None:
        """Handle passive observation routing based on channel ID and author filtering"""
        if not self.multi_service_sink:
            logger.warning("No multi_service_sink available for passive observation")
            return
            
        # Get environment variables for channel filtering. When running in CLI
        # mode the Discord variables may not be set, so fall back to 'cli'.
        default_channel_id = os.getenv("DISCORD_CHANNEL_ID") or "cli"
        deferral_channel_id = os.getenv("DISCORD_DEFERRAL_CHANNEL_ID")
        wa_discord_user = os.getenv("WA_DISCORD_USER", DEFAULT_WA)
        
        # Route messages based on channel and author
        if msg.channel_id == default_channel_id and not self._is_agent_message(msg):
            # Create passive observation result for default channel
            await self._create_passive_observation_result(msg)
        elif msg.channel_id == deferral_channel_id and msg.author_name == wa_discord_user:
            # Add to fetch feedback queue for WA messages in deferral channel
            await self._add_to_feedback_queue(msg)
        else:
            # Ignore messages from other channels or from agent itself
            logger.debug("Ignoring message from channel %s, author %s", msg.channel_id, msg.author_name)

    def _is_agent_message(self, msg: IncomingMessage) -> bool:
        """Check if message is from the agent itself"""
        if self.agent_id and msg.author_id == self.agent_id:
            return True
        return msg.is_bot  # Additional check for bot messages

    async def _create_passive_observation_result(self, msg: IncomingMessage) -> None:
        """Create passive observation result via the observation callback"""
        try:
            if self.on_observe:
                # Create observation payload similar to Discord observer
                payload = {
                    "message": {
                        "message_id": msg.message_id,
                        "content": msg.content,
                        "author_id": msg.author_id,
                        "author_name": msg.author_name,
                        "channel_id": msg.channel_id,
                        "timestamp": msg.timestamp,
                        "is_bot": msg.is_bot,
                        "is_dm": msg.is_dm,
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
        """Add WA message to fetch feedback queue via multi-service sink"""
        try:
            # For WA feedback messages, we can use the multi-service sink to route appropriately
            # This creates a message action that will be processed by the communication services
            if self.multi_service_sink:
                # Send the feedback message content to be processed
                # The multi-service sink will handle routing to appropriate handlers
                success = await self.multi_service_sink.send_message(
                    handler_name="CLIObserver",
                    channel_id=msg.channel_id,
                    content=f"[WA_FEEDBACK] {msg.content}",
                    metadata={
                        "message_type": "wa_feedback",
                        "original_message_id": msg.message_id,
                        "wa_user": msg.author_name,
                        "source": "cli_observer"
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
        import socket
        recall_ids = {f"channel/{socket.gethostname()}"}
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
