import logging
import os
import asyncio
from typing import Callable, Awaitable, Dict, Any, Optional

from ciris_engine.runtime.base_runtime import IncomingMessage # Import IncomingMessage
from .base import Service
from .discord_event_queue import DiscordEventQueue # Import the generic DiscordEventQueue

logger = logging.getLogger(__name__)


class DiscordObserver(Service):
    """
    Observes IncomingMessage objects from a DiscordEventQueue, converts them into an OBSERVATION
    payload, and forwards it to the agent via `on_observe` for task creation.
    """

    def __init__(
        self,
        on_observe: Callable[[Dict[str, Any]], Awaitable[None]], # This callback will create the Task
        message_queue: DiscordEventQueue[IncomingMessage], # Use DiscordEventQueue[IncomingMessage]
        monitored_channel_id: Optional[str] = None,
    ):
        super().__init__()
        self.on_observe = on_observe
        self.message_queue = message_queue # Store the DiscordEventQueue[IncomingMessage]
        self._poll_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

        env_id = os.getenv("DISCORD_CHANNEL_ID")
        if monitored_channel_id is None and env_id:
            monitored_channel_id = env_id.strip()

        self.monitored_channel_id: Optional[str] = monitored_channel_id

    async def start(self):
        await super().start()
        if self.message_queue: # Check if the new message_queue is provided
            self._poll_task = asyncio.create_task(self._poll_events())

    async def stop(self):
        if self._poll_task:
            self._stop_event.set()
            # Add a small timeout to allow the poll_task to finish gracefully
            try:
                await asyncio.wait_for(self._poll_task, timeout=1.0)
            except asyncio.TimeoutError:
                logger.warning("DiscordObserver poll_task did not finish in time.")
                self._poll_task.cancel() # Force cancel if it doesn't stop
            except Exception as e:
                logger.error(f"Error stopping DiscordObserver poll_task: {e}")
            self._poll_task = None
        await super().stop()

    async def _poll_events(self) -> None:
        """Polls IncomingMessage objects from the message_queue."""
        while not self._stop_event.is_set():
            try:
                # Dequeue IncomingMessage object from DiscordEventQueue
                incoming_msg = await asyncio.wait_for(self.message_queue.dequeue(), timeout=0.1) # Use dequeue method
                if incoming_msg:
                    await self.handle_incoming_message(incoming_msg)
                    # No task_done() for DiscordEventQueue as it's a wrapper around asyncio.Queue
                    # asyncio.Queue's task_done is typically used if join() is called on the queue.
            except asyncio.TimeoutError:
                continue # No message, continue polling
            except Exception as e:
                logger.exception(f"DiscordObserver: Error during event polling: {e}")
                # Add a small delay to prevent rapid looping on persistent errors
                await asyncio.sleep(1)


    async def handle_incoming_message(self, msg: IncomingMessage) -> None:
        """
        Translate an IncomingMessage into an OBSERVATION payload for task creation.
        """
        if not isinstance(msg, IncomingMessage):
            logger.warning(f"DiscordObserver: Received non-IncomingMessage object: {type(msg)}. Skipping.")
            return

        # Skip if a specific channel is configured and this is not it
        if self.monitored_channel_id and msg.channel_id != self.monitored_channel_id:
            logger.debug(f"DiscordObserver: Ignoring message from unmonitored channel: {msg.channel_id} for message {msg.message_id}")
            return

        # Construct the payload for the on_observe callback, which will create the Task
        # This payload should contain all necessary info for Task creation.
        payload: Dict[str, Any] = {
            "type": "OBSERVATION", # Indicates the nature of the event
            "message_id": msg.message_id,
            "content": msg.content,
            "context": { # This will become Task.context
                "origin_service": "discord", # Hardcode as this observer is for discord
                "author_id": msg.author_id,
                "author_name": msg.author_name,
                "channel_id": msg.channel_id,
                # Add any other relevant fields from IncomingMessage that should be in Task.context
            },
            "task_description": ( # This will become Task.description
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
