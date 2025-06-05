import asyncio
from typing import Callable, Awaitable, Dict, Any, Optional, List
import os
import logging

from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.schemas.graph_schemas_v1 import GraphScope, GraphNode, NodeType
from ciris_engine.utils.constants import DEFAULT_WA
from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink

logger = logging.getLogger(__name__)

PASSIVE_CONTEXT_LIMIT = 10

class APIObserver:
    def __init__(
        self,
        on_observe: Callable[[Dict[str, Any]], Awaitable[None]],
        memory_service: Optional[Any] = None,
        agent_id: Optional[str] = None,
        multi_service_sink: Optional[MultiServiceActionSink] = None,
        api_adapter: Optional[Any] = None,
    ) -> None:
        self.on_observe = on_observe
        self.memory_service = memory_service
        self.agent_id = agent_id
        self.multi_service_sink = multi_service_sink
        self.api_adapter = api_adapter
        self._history: list[IncomingMessage] = []

    async def start(self) -> None:
        # APIObserver doesn't need to start a polling task - it only handles direct message calls
        pass

    async def stop(self) -> None:
        # APIObserver doesn't have background tasks to stop
        pass

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
        from ciris_engine.utils.constants import (
            API_CHANNEL_ID,
            API_DEFERRAL_CHANNEL_ID,
            WA_API_USER,
            DEFAULT_WA,
        )

        default_channel_id = API_CHANNEL_ID
        deferral_channel_id = API_DEFERRAL_CHANNEL_ID
        wa_api_user = WA_API_USER or DEFAULT_WA
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
        """Create task and thought for passive observation."""
        try:
            from datetime import datetime, timezone
            import uuid
            from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought
            from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus
            from ciris_engine import persistence

            task = Task(
                task_id=str(uuid.uuid4()),
                description=f"Respond to message from @{msg.author_name} in #{msg.channel_id}: '{msg.content}'",
                status=TaskStatus.PENDING,
                priority=0,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
                context={
                    "channel_id": msg.channel_id,
                    "author_id": msg.author_id,
                    "author_name": msg.author_name,
                    "message_id": msg.message_id,
                    "origin_service": "api",
                    "observation_type": "passive",
                    "recent_messages": [
                        {
                            "id": m.message_id,
                            "content": m.content,
                            "author_id": m.author_id,
                            "author_name": m.author_name,
                            "channel_id": m.channel_id,
                            "timestamp": getattr(m, "timestamp", "n/a"),
                        }
                        for m in self._history[-PASSIVE_CONTEXT_LIMIT:]
                    ],
                }
            )
            channel_id = (
                task.context.get("channel_id")
                if isinstance(task.context, dict)
                else getattr(task.context, "channel_id", None)
            )
            assert channel_id, "Task context must include a non-empty channel_id"
            persistence.add_task(task)

            thought = Thought(
                thought_id=str(uuid.uuid4()),
                source_task_id=task.task_id,
                thought_type="observation",
                status=ThoughtStatus.PENDING,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
                round_number=0,
                content=f"User @{msg.author_name} said: {msg.content}",
                context=(
                    task.context
                    if isinstance(task.context, dict)
                    else task.context.model_dump() if task.context else {}
                )
            )
            thought_channel_id = (
                thought.context.get("channel_id")
                if isinstance(thought.context, dict)
                else getattr(thought.context, "channel_id", None)
            )
            assert thought_channel_id, "Thought context must include a non-empty channel_id"
            persistence.add_thought(thought)

            logger.info(f"Created observation task {task.task_id} and thought {thought.thought_id} for message {msg.message_id}")

        except Exception as e:
            logger.error(f"Error creating observation task: {e}", exc_info=True)

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
        for m in self._history[-PASSIVE_CONTEXT_LIMIT:]:
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
        all_messages: List[Any] = []
        
        # Get recent input messages from history
        recent_history = self._history[-limit*2:]  # Get more history to account for responses
        
        for msg in recent_history:
            # Add the user's input message
            all_messages.append({
                "id": msg.message_id,
                "content": msg.content,
                "author_id": msg.author_id,
                "timestamp": getattr(msg, "timestamp", "n/a"),
            })
            
            # Add any agent responses for this channel
            if self.api_adapter and hasattr(self.api_adapter, 'channel_messages'):
                channel_responses = self.api_adapter.channel_messages.get(msg.channel_id, [])
                
                # Add responses that came after this message (simple approach for now)
                for response in channel_responses:
                    all_messages.append(response)
        
        # Remove duplicates and sort by timestamp if available
        seen_ids = set()
        unique_messages: List[Any] = []
        for msg in all_messages:
            if msg["id"] not in seen_ids:
                seen_ids.add(msg["id"])
                unique_messages.append(msg)
        
        # Return the most recent messages up to the limit
        return unique_messages[-limit:]
