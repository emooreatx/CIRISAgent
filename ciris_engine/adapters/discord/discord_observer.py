import logging
import os
import asyncio
from typing import Callable, Awaitable, Dict, Any, Optional
from ciris_engine.schemas.graph_schemas_v1 import GraphScope, GraphNode, NodeType

from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.schemas.service_actions_v1 import FetchMessagesAction
from ciris_engine.utils.constants import DEFAULT_WA
from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink

logger = logging.getLogger(__name__)


class DiscordObserver:
    """
    Observes IncomingMessage objects directly from Discord adapter, converts them into OBSERVATION
    payloads, and forwards them to the agent via MultiServiceSink. Uses only MultiServiceSink 
    architecture without event queues.
    """

    def __init__(
        self,
        monitored_channel_id: Optional[str] = None,
        memory_service: Optional[Any] = None,
        agent_id: Optional[str] = None,
        multi_service_sink: Optional[MultiServiceActionSink] = None,
    ):
        self.memory_service = memory_service
        self.agent_id = agent_id
        self.multi_service_sink = multi_service_sink
        self._history: list[IncomingMessage] = []

        from ciris_engine.config.config_manager import get_config

        if monitored_channel_id is None:
            monitored_channel_id = get_config().discord_channel_id
        self.monitored_channel_id: Optional[str] = monitored_channel_id

    async def start(self):
        """Start the observer - no polling needed since we receive messages directly."""
        logger.info("DiscordObserver started - ready to receive messages directly from Discord adapter")

    async def stop(self):
        """Stop the observer - no background tasks to clean up."""
        logger.info("DiscordObserver stopped")

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
        from ciris_engine.config.config_manager import get_config
        from ciris_engine.utils.constants import (
            DISCORD_DEFERRAL_CHANNEL_ID,
            DEFAULT_WA,
        )

        default_channel_id = get_config().discord_channel_id
        deferral_channel_id = DISCORD_DEFERRAL_CHANNEL_ID
        wa_discord_user = DEFAULT_WA
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
        """Create task and thought for passive observation."""
        try:
            from datetime import datetime, timezone
            import uuid
            from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought
            from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus
            from ciris_engine import persistence

            # Create task for this observation
            task = Task(
                task_id=str(uuid.uuid4()),
                description=f"Respond to message from @{msg.author_name} in #{msg.channel_id}: '{msg.content[:100]}...'",
                status=TaskStatus.PENDING,
                priority=0,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
                context={
                    "channel_id": msg.channel_id,
                    "author_id": msg.author_id,
                    "author_name": msg.author_name,
                    "message_id": msg.message_id,
                    "origin_service": "discord",
                    "observation_type": "passive"
                }
            )
            persistence.add_task(task)

            # Create thought for this task
            thought = Thought(
                thought_id=str(uuid.uuid4()),
                source_task_id=task.task_id,
                thought_type="observation",
                status=ThoughtStatus.PENDING,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
                round_number=0,
                content=f"User @{msg.author_name} said: {msg.content}",
                context=task.context
            )
            persistence.add_thought(thought)

            logger.info(f"Created observation task {task.task_id} and thought {thought.thought_id} for message {msg.message_id}")

        except Exception as e:
            logger.error(f"Error creating observation task: {e}", exc_info=True)

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
                    # Determine node type based on ID prefix
                    if rid.startswith("channel/"):
                        node_type = NodeType.CHANNEL
                    elif rid.startswith("user/"):
                        node_type = NodeType.USER
                    else:
                        node_type = NodeType.CONCEPT
                    
                    node = GraphNode(id=rid, type=node_type, scope=scope)
                    await self.memory_service.recall(node)
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
