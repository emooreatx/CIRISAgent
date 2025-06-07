import asyncio
import logging
import os
from typing import Callable, Awaitable, Dict, Any, Optional
from ciris_engine.schemas.graph_schemas_v1 import GraphScope, GraphNode, NodeType

from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.schemas.service_actions_v1 import FetchMessagesAction
from ciris_engine.utils.constants import DEFAULT_WA
from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink
from ciris_engine.secrets.service import SecretsService


logger = logging.getLogger(__name__)

PASSIVE_CONTEXT_LIMIT = 10

class CLIObserver:
    """
    Observer that converts CLI input events into observation payloads.
    Includes adaptive filtering for message prioritization.
    """

    def __init__(
        self,
        on_observe: Callable[[Dict[str, Any]], Awaitable[None]],
        memory_service: Optional[Any] = None,
        agent_id: Optional[str] = None,
        multi_service_sink: Optional[MultiServiceActionSink] = None,
        filter_service: Optional[Any] = None,
        secrets_service: Optional[SecretsService] = None,
        *,
        interactive: bool = True,
    ) -> None:
        self.on_observe = on_observe
        self.memory_service = memory_service
        self.agent_id = agent_id
        self.multi_service_sink = multi_service_sink
        self.filter_service = filter_service
        self.secrets_service = secrets_service or SecretsService()
        self.interactive = interactive
        self._input_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._history: list[IncomingMessage] = []

    async def start(self) -> None:
        """Start the observer and optional input loop."""
        logger.info("CLIObserver started")
        if self.interactive and self._input_task is None:
            self._input_task = asyncio.create_task(self._input_loop())

    async def stop(self) -> None:
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
        
        # Check if this is the agent's own message
        is_agent_message = self.agent_id and msg.author_id == self.agent_id
        
        # Process message for secrets detection and replacement (for all messages)
        processed_msg = await self._process_message_secrets(msg)
        
        # Add ALL messages to history (including agent's own)
        self._history.append(processed_msg)
        
        # If it's the agent's message, stop here (no task creation)
        if is_agent_message:
            logger.debug("Added agent's own message %s to history (no task created)", msg.message_id)
            return
        
        # Apply adaptive filtering to determine message priority and processing
        filter_result = await self._apply_message_filtering(msg)
        if not filter_result.should_process:
            logger.debug(f"Message {msg.message_id} filtered out: {filter_result.reasoning}")
            return
        
        # Add filter context to message for downstream processing
        processed_msg._filter_priority = filter_result.priority
        processed_msg._filter_context = filter_result.context_hints
        processed_msg._filter_reasoning = filter_result.reasoning
        
        # Process based on priority
        if filter_result.priority.value in ['critical', 'high']:
            # Immediate processing for high-priority messages
            logger.info(f"Processing {filter_result.priority.value} priority message {msg.message_id}: {filter_result.reasoning}")
            await self._handle_priority_observation(processed_msg, filter_result)
        else:
            # Normal processing for medium/low priority
            await self._handle_passive_observation(processed_msg)
            
        await self._recall_context(processed_msg)

    async def _process_message_secrets(self, msg: IncomingMessage) -> IncomingMessage:
        """Process message content for secrets detection and replacement."""
        try:
            # Process the message content for secrets
            processed_content, secret_refs = await self.secrets_service.process_incoming_text(
                msg.content,
                context_hint=f"CLI message from {msg.author_id}",
                source_message_id=msg.message_id
            )
            
            # Create new message with processed content
            processed_msg = IncomingMessage(
                message_id=msg.message_id,
                content=processed_content,
                author_id=msg.author_id,
                author_name=msg.author_name,
                channel_id=msg.channel_id,
                timestamp=getattr(msg, 'timestamp', None),
                is_bot=getattr(msg, 'is_bot', False),
                is_dm=getattr(msg, 'is_dm', False),
                mentions_agent=getattr(msg, 'mentions_agent', False),
                reply_to_message_id=getattr(msg, 'reply_to_message_id', None)
            )
            
            # Store secret references on the message for context
            if secret_refs:
                processed_msg._detected_secrets = [
                    {
                        "uuid": ref.secret_uuid,
                        "context_hint": ref.context_hint,
                        "sensitivity": ref.sensitivity
                    }
                    for ref in secret_refs
                ]
                logger.info(f"Detected and processed {len(secret_refs)} secrets in CLI message {msg.message_id}")
            
            return processed_msg
            
        except Exception as e:
            logger.error(f"Error processing secrets in CLI message {msg.message_id}: {e}")
            # Return original message if processing fails
            return msg

    async def _apply_message_filtering(self, msg: IncomingMessage):
        """Apply adaptive filtering to incoming message"""
        if not self.filter_service:
            # No filter service available - create default result
            from ciris_engine.schemas.filter_schemas_v1 import FilterResult, FilterPriority
            return FilterResult(
                message_id=msg.message_id,
                priority=FilterPriority.MEDIUM,
                triggered_filters=[],
                should_process=True,
                reasoning="No filter service available - processing normally"
            )
        
        try:
            # Apply filtering to the message
            filter_result = await self.filter_service.filter_message(
                message=msg,
                adapter_type="cli"
            )
            
            # Log filtering results for debugging
            if filter_result.triggered_filters:
                logger.debug(f"Message {msg.message_id} triggered filters: {filter_result.triggered_filters}")
            
            return filter_result
            
        except Exception as e:
            logger.error(f"Error applying filter to message {msg.message_id}: {e}")
            # Return safe default on error
            from ciris_engine.schemas.filter_schemas_v1 import FilterResult, FilterPriority
            return FilterResult(
                message_id=msg.message_id,
                priority=FilterPriority.MEDIUM,
                triggered_filters=[],
                should_process=True,
                reasoning=f"Filter error, processing normally: {e}"
            )

    async def _handle_priority_observation(self, msg: IncomingMessage, filter_result) -> None:
        """Handle high-priority messages with immediate processing"""
        from ciris_engine.config.config_manager import get_config
        from ciris_engine.utils.constants import (
            DISCORD_DEFERRAL_CHANNEL_ID,
            DEFAULT_WA,
        )

        config_discord_channel_id = get_config().discord_channel_id
        deferral_channel_id = DISCORD_DEFERRAL_CHANNEL_ID
        wa_discord_user = DEFAULT_WA
        
        if (msg.channel_id == "cli" or msg.channel_id == config_discord_channel_id) and not self._is_agent_message(msg):
            # Create high-priority observation with enhanced context
            await self._create_priority_observation_result(msg, filter_result)
        elif msg.channel_id == deferral_channel_id and msg.author_name == wa_discord_user:
            await self._add_to_feedback_queue(msg)
        else:
            logger.debug("Ignoring priority message from channel %s, author %s", msg.channel_id, msg.author_name)

    async def _handle_passive_observation(self, msg: IncomingMessage) -> None:
        """Handle passive observation routing based on channel ID and author filtering"""
        
        # Get environment variables for channel filtering
        from ciris_engine.config.config_manager import get_config
        from ciris_engine.utils.constants import (
            DISCORD_DEFERRAL_CHANNEL_ID,
            DEFAULT_WA,
        )

        config_discord_channel_id = get_config().discord_channel_id
        deferral_channel_id = DISCORD_DEFERRAL_CHANNEL_ID
        wa_discord_user = DEFAULT_WA
        
        logger.debug(f"Message channel_id: {msg.channel_id}")
        logger.debug(f"Config discord_channel_id: {config_discord_channel_id}")
        
        # Route messages based on channel and author
        # For CLI messages (channel_id == "cli"), always process them
        # For Discord messages, only process if they match the configured channel
        if (msg.channel_id == "cli" or msg.channel_id == config_discord_channel_id) and not self._is_agent_message(msg):
            # Create passive observation result for CLI or configured Discord channel
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
                    "origin_service": "cli",
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

    async def _create_priority_observation_result(self, msg: IncomingMessage, filter_result) -> None:
        """Create task and thought for priority observation with enhanced filter context."""
        try:
            from datetime import datetime, timezone
            import uuid
            from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought
            from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus
            from ciris_engine import persistence

            # Determine task priority based on filter result
            task_priority = 10 if filter_result.priority.value == 'critical' else 5
            
            # Create task for this priority observation
            task = Task(
                task_id=str(uuid.uuid4()),
                description=f"PRIORITY: Respond to {filter_result.priority.value} message from @{msg.author_name}: '{msg.content}'",
                status=TaskStatus.PENDING,
                priority=task_priority,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
                context={
                    "channel_id": msg.channel_id,
                    "author_id": msg.author_id,
                    "author_name": msg.author_name,
                    "message_id": msg.message_id,
                    "origin_service": "cli",
                    "observation_type": "priority",
                    "filter_priority": filter_result.priority.value,
                    "filter_reasoning": filter_result.reasoning,
                    "triggered_filters": filter_result.triggered_filters,
                    "filter_confidence": filter_result.confidence,
                    "filter_context": filter_result.context_hints,
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

            # Create thought for this task with filter context
            thought = Thought(
                thought_id=str(uuid.uuid4()),
                source_task_id=task.task_id,
                thought_type="observation",
                status=ThoughtStatus.PENDING,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
                round_number=0,
                content=f"PRIORITY ({filter_result.priority.value}): User @{msg.author_name} said: {msg.content} | Filter: {filter_result.reasoning}",
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

            logger.info(f"Created PRIORITY observation task {task.task_id} and thought {thought.thought_id} for {filter_result.priority.value} message {msg.message_id}")

        except Exception as e:
            logger.error(f"Error creating priority observation task: {e}", exc_info=True)

    async def _add_to_feedback_queue(self, msg: IncomingMessage) -> None:
        """Add WA message to fetch feedback queue via multi-service sink"""
        try:
            if self.multi_service_sink:
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
