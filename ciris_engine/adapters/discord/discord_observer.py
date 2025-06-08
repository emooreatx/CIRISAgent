import logging
import os
import asyncio
from typing import Callable, Awaitable, Dict, Any, Optional
from ciris_engine.schemas.graph_schemas_v1 import GraphScope, GraphNode, NodeType

from ciris_engine.schemas.foundational_schemas_v1 import DiscordMessage
from ciris_engine.schemas.service_actions_v1 import FetchMessagesAction
from ciris_engine.utils.constants import DEFAULT_WA
from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink
from ciris_engine.secrets.service import SecretsService

logger = logging.getLogger(__name__)

PASSIVE_CONTEXT_LIMIT = 10


class DiscordObserver:
    """
    Observes DiscordMessage objects directly from Discord adapter, converts them into OBSERVATION
    payloads, and forwards them to the agent via MultiServiceSink. Uses only MultiServiceSink 
    architecture without event queues. Includes adaptive filtering for message prioritization.
    """

    def __init__(
        self,
        monitored_channel_id: Optional[str] = None,
        memory_service: Optional[Any] = None,
        agent_id: Optional[str] = None,
        multi_service_sink: Optional[MultiServiceActionSink] = None,
        filter_service: Optional[Any] = None,
        secrets_service: Optional[SecretsService] = None,
    ) -> None:
        self.memory_service = memory_service
        self.agent_id = agent_id
        self.multi_service_sink = multi_service_sink
        self.filter_service = filter_service
        self.secrets_service = secrets_service or SecretsService()
        self._history: list[DiscordMessage] = []

        from ciris_engine.config.config_manager import get_config

        if monitored_channel_id is None:
            monitored_channel_id = get_config().discord_channel_id
        self.monitored_channel_id: Optional[str] = monitored_channel_id

    async def start(self) -> None:
        """Start the observer - no polling needed since we receive messages directly."""
        logger.info("DiscordObserver started - ready to receive messages directly from Discord adapter")

    async def stop(self) -> None:
        """Stop the observer - no background tasks to clean up."""
        logger.info("DiscordObserver stopped")

    async def handle_incoming_message(self, msg: DiscordMessage) -> None:
        if not isinstance(msg, DiscordMessage):
            logger.warning("DiscordObserver received non-DiscordMessage")
            return
        if self.monitored_channel_id and msg.channel_id != self.monitored_channel_id:
            logger.debug("Ignoring message from channel %s (not monitored)", msg.channel_id)
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

    async def _process_message_secrets(self, msg: DiscordMessage) -> DiscordMessage:
        """Process message content for secrets detection and replacement."""
        try:
            # Process the message content for secrets
            processed_content, secret_refs = await self.secrets_service.process_incoming_text(
                msg.content,
                context_hint=f"Discord message from {msg.author_name} in channel {msg.channel_id}",
                source_message_id=msg.message_id
            )
            
            # Create new message with processed content
            processed_msg = DiscordMessage(
                message_id=msg.message_id,
                content=processed_content,
                author_id=msg.author_id,
                author_name=msg.author_name,
                channel_id=msg.channel_id,
                guild_id=getattr(msg, 'guild_id', None),
                timestamp=msg.timestamp,
                is_bot=msg.is_bot,
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
                logger.info(f"Detected and processed {len(secret_refs)} secrets in message {msg.message_id}")
            
            return processed_msg
            
        except Exception as e:
            logger.error(f"Error processing secrets in message {msg.message_id}: {e}")
            # Return original message if processing fails
            return msg

    async def _apply_message_filtering(self, msg: DiscordMessage):
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
                adapter_type="discord"
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

    async def _handle_priority_observation(self, msg: DiscordMessage, filter_result) -> None:
        """Handle high-priority messages with immediate processing"""
        from ciris_engine.config.config_manager import get_config
        from ciris_engine.utils.constants import (
            DISCORD_DEFERRAL_CHANNEL_ID,
            DEFAULT_WA,
        )

        default_channel_id = get_config().discord_channel_id
        deferral_channel_id = DISCORD_DEFERRAL_CHANNEL_ID
        wa_discord_user = DEFAULT_WA
        authorized_user_id = "537080239679864862"  # Your Discord user ID
        
        if msg.channel_id == default_channel_id:
            # Create high-priority observation with enhanced context
            await self._create_priority_observation_result(msg, filter_result)
        elif msg.channel_id == deferral_channel_id and (msg.author_id == authorized_user_id or msg.author_name == wa_discord_user):
            await self._add_to_feedback_queue(msg)
        else:
            logger.debug("Ignoring priority message from channel %s, author %s (ID: %s)", msg.channel_id, msg.author_name, msg.author_id)

    async def _handle_passive_observation(self, msg: DiscordMessage) -> None:
        from ciris_engine.config.config_manager import get_config
        from ciris_engine.utils.constants import (
            DISCORD_DEFERRAL_CHANNEL_ID,
            DEFAULT_WA,
        )

        default_channel_id = get_config().discord_channel_id
        deferral_channel_id = DISCORD_DEFERRAL_CHANNEL_ID
        wa_discord_user = DEFAULT_WA
        authorized_user_id = "537080239679864862"  # Your Discord user ID
        
        if msg.channel_id == default_channel_id:
            await self._create_passive_observation_result(msg)
        elif msg.channel_id == deferral_channel_id and (msg.author_id == authorized_user_id or msg.author_name == wa_discord_user):
            await self._add_to_feedback_queue(msg)
        else:
            logger.debug("Ignoring message from channel %s, author %s (ID: %s)", msg.channel_id, msg.author_name, msg.author_id)


    async def _create_passive_observation_result(self, msg: DiscordMessage) -> None:
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
                    "origin_service": "discord",
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

    async def _create_priority_observation_result(self, msg: DiscordMessage, filter_result) -> None:
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
                    "origin_service": "discord",
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

    async def _add_to_feedback_queue(self, msg: DiscordMessage) -> None:
        """Process guidance/feedback from WA in deferral channel."""
        try:
            from datetime import datetime, timezone
            import uuid
            import re
            from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought
            from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus
            from ciris_engine import persistence

            # Check if this is a reply to a deferral report
            thought_id_match = None
            referenced_thought_id = None
            
            # First check if this message is replying to another message
            if hasattr(msg, '_raw_message') and msg._raw_message and hasattr(msg._raw_message, 'reference'):
                ref = msg._raw_message.reference
                if ref and ref.resolved:
                    # Check if the referenced message contains a thought ID
                    ref_content = ref.resolved.content
                    thought_id_pattern = r'Thought ID:\s*`([a-f0-9-]+)`'
                    match = re.search(thought_id_pattern, ref_content)
                    if match:
                        referenced_thought_id = match.group(1)
                        logger.info(f"Found reply to deferral for thought ID: {referenced_thought_id}")
            
            # If not a reply, check if the message itself mentions a thought ID
            if not referenced_thought_id:
                thought_id_pattern = r'(?:thought\s+id|thought_id|re:\s*thought)[\s:]*([a-f0-9-]+)'
                match = re.search(thought_id_pattern, msg.content, re.IGNORECASE)
                if match:
                    referenced_thought_id = match.group(1)
                    logger.info(f"Found thought ID reference in message: {referenced_thought_id}")
            
            if referenced_thought_id:
                # This is guidance for a specific deferred thought
                # Find the original thought and its task
                original_thought = persistence.get_thought(referenced_thought_id)
                if original_thought and original_thought.status == ThoughtStatus.DEFERRED:
                    # Reactivate the original task
                    original_task = persistence.get_task(original_thought.source_task_id)
                    if original_task:
                        persistence.update_task_status(original_task.task_id, TaskStatus.ACTIVE)
                        logger.info(f"Reactivated task {original_task.task_id} due to guidance")
                        
                        # Create a new child thought for the guidance
                        # Reset round_number to 0 to give fresh rounds after deferral
                        guidance_thought = Thought(
                            thought_id=str(uuid.uuid4()),
                            source_task_id=original_task.task_id,
                            parent_thought_id=referenced_thought_id,
                            thought_type="guidance",
                            status=ThoughtStatus.PENDING,
                            created_at=datetime.now(timezone.utc).isoformat(),
                            updated_at=datetime.now(timezone.utc).isoformat(),
                            round_number=0,  # Reset to 0 for fresh processing after guidance
                            content=f"Guidance from @{msg.author_name}: {msg.content}",
                            context={
                                **original_thought.context,
                                "guidance_message_id": msg.message_id,
                                "guidance_author": msg.author_name,
                                "guidance_content": msg.content,
                                "is_guidance_response": True,
                                "original_round_number": original_thought.round_number  # Store original for reference
                            }
                        )
                        persistence.add_thought(guidance_thought)
                        logger.info(f"Created guidance thought {guidance_thought.thought_id} as child of deferred thought {referenced_thought_id}")
                        return
                else:
                    logger.warning(f"Thought {referenced_thought_id} not found or not deferred")
            
            # If we get here, it's unsolicited guidance - create a new task
            task = Task(
                task_id=str(uuid.uuid4()),
                description=f"Process unsolicited guidance from @{msg.author_name}: '{msg.content}'",
                status=TaskStatus.PENDING,
                priority=8,  # High priority for guidance
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
                context={
                    "channel_id": msg.channel_id,
                    "author_id": msg.author_id,
                    "author_name": msg.author_name,
                    "message_id": msg.message_id,
                    "origin_service": "discord",
                    "observation_type": "unsolicited_guidance",
                    "is_guidance": True,
                    "guidance_content": msg.content,
                }
            )
            persistence.add_task(task)

            # Create thought for this guidance
            thought = Thought(
                thought_id=str(uuid.uuid4()),
                source_task_id=task.task_id,
                thought_type="observation",
                status=ThoughtStatus.PENDING,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
                round_number=0,
                content=f"Unsolicited guidance from @{msg.author_name}: {msg.content}",
                context=task.context
            )
            persistence.add_thought(thought)

            logger.info(f"Created unsolicited guidance task {task.task_id} and thought {thought.thought_id}")
                
        except Exception as e:
            logger.error(f"Error processing guidance message {msg.message_id}: {e}", exc_info=True)

    async def _recall_context(self, msg: DiscordMessage) -> None:
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
