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
from ciris_engine.adapters.base_observer import BaseObserver

logger = logging.getLogger(__name__)

PASSIVE_CONTEXT_LIMIT = 10


class DiscordObserver(BaseObserver[DiscordMessage]):
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
        communication_service: Optional[Any] = None,
    ) -> None:
        super().__init__(
            on_observe=lambda _: None,
            memory_service=memory_service,
            agent_id=agent_id,
            multi_service_sink=multi_service_sink,
            filter_service=filter_service,
            secrets_service=secrets_service,
            origin_service="discord",
        )
        self.communication_service = communication_service

        from ciris_engine.config.config_manager import get_config

        if monitored_channel_id is None:
            monitored_channel_id = get_config().discord_channel_id
        self.monitored_channel_id: Optional[str] = monitored_channel_id

    async def _send_deferral_message(self, content: str) -> None:
        """Send a message to the deferral channel."""
        if not self.communication_service:
            logger.warning("No communication service available to send deferral message")
            return
        
        from ciris_engine.config.config_manager import get_config
        deferral_channel_id = get_config().discord_deferral_channel_id
        
        if not deferral_channel_id:
            logger.warning("No deferral channel configured")
            return
        
        try:
            await self.communication_service.send_message(deferral_channel_id, content)
            logger.debug(f"Sent deferral response: {content[:100]}...")
        except Exception as e:
            logger.error(f"Failed to send deferral message: {e}")

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
        # Accept messages from both monitored channel and deferral channel
        from ciris_engine.config.config_manager import get_config
        config = get_config()
        deferral_channel_id = config.discord_deferral_channel_id
        
        # Check if message is from a monitored channel
        is_from_monitored = (self.monitored_channel_id and msg.channel_id == self.monitored_channel_id)
        is_from_deferral = (deferral_channel_id and msg.channel_id == deferral_channel_id)
        
        if not (is_from_monitored or is_from_deferral):
            logger.debug("Ignoring message from channel %s (not monitored or deferral)", msg.channel_id)
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
        filter_result = await self._apply_message_filtering(msg, "discord")
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


    async def _handle_priority_observation(self, msg: DiscordMessage, filter_result) -> None:
        """Handle high-priority messages with immediate processing"""
        from ciris_engine.config.config_manager import get_config
        from ciris_engine.utils.constants import (
            DEFAULT_WA,
        )

        config = get_config()
        default_channel_id = config.discord_channel_id
        deferral_channel_id = config.discord_deferral_channel_id
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
            DEFAULT_WA,
        )

        config = get_config()
        default_channel_id = config.discord_channel_id
        deferral_channel_id = config.discord_deferral_channel_id
        wa_discord_user = DEFAULT_WA
        authorized_user_id = "537080239679864862"  # Your Discord user ID
        
        if msg.channel_id == default_channel_id:
            await self._create_passive_observation_result(msg)
        elif msg.channel_id == deferral_channel_id and (msg.author_id == authorized_user_id or msg.author_name == wa_discord_user):
            await self._add_to_feedback_queue(msg)
        else:
            logger.debug("Ignoring message from channel %s, author %s (ID: %s)", msg.channel_id, msg.author_name, msg.author_id)


    async def _add_to_feedback_queue(self, msg: DiscordMessage) -> None:
        """Process guidance/feedback from WA in deferral channel."""
        try:
            # First validate that the user is a wise authority
            from ciris_engine.utils.constants import DEFAULT_WA
            wa_discord_user = DEFAULT_WA
            authorized_user_id = "537080239679864862"  # Your Discord user ID
            
            is_wise_authority = (msg.author_id == authorized_user_id or msg.author_name == wa_discord_user)
            
            if not is_wise_authority:
                error_msg = f"🚫 **Not Authorized**: User `{msg.author_name}` (ID: `{msg.author_id}`) is not a Wise Authority. Not proceeding with guidance processing."
                logger.warning(f"Non-WA user {msg.author_name} ({msg.author_id}) attempted to provide guidance")
                await self._send_deferral_message(error_msg)
                return
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
            logger.info(f"Checking reply detection for message {msg.message_id}")
            if hasattr(msg, 'raw_message') and msg.raw_message:
                logger.info(f"Message has raw_message: {msg.raw_message.id}")
                if hasattr(msg.raw_message, 'reference'):
                    ref = msg.raw_message.reference
                    logger.info(f"Message reference: {ref}")
                    if ref and ref.resolved:
                        # Check if the referenced message contains a thought ID
                        ref_content = ref.resolved.content
                        logger.info(f"Referenced message content: {ref_content}")
                        thought_id_pattern = r'\*\*Thought ID:\*\*\s*`([a-f0-9-]+)`'
                        match = re.search(thought_id_pattern, ref_content)
                        if match:
                            referenced_thought_id = match.group(1)
                            logger.info(f"Found reply to deferral for thought ID: {referenced_thought_id}")
                        else:
                            logger.info(f"No thought ID pattern found in referenced message")
                    else:
                        logger.info(f"Reference not resolved or None")
                else:
                    logger.info(f"Message has no reference attribute")
            else:
                logger.info(f"Message has no raw_message")
            
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
                original_thought = persistence.get_thought_by_id(referenced_thought_id)
                if original_thought is None:
                    error_msg = f"❌ **Error**: Thought `{referenced_thought_id}` not found in database"
                    logger.warning(f"Thought {referenced_thought_id} not found in database")
                    await self._send_deferral_message(error_msg)
                elif original_thought.status != ThoughtStatus.DEFERRED:
                    error_msg = f"❌ **Error**: Thought `{referenced_thought_id}` found but status is `{original_thought.status}`, not `DEFERRED`"
                    logger.warning(f"Thought {referenced_thought_id} found but status is {original_thought.status}, not DEFERRED")
                    await self._send_deferral_message(error_msg)
                else:
                    # Reactivate the original task  
                    original_task = persistence.get_task_by_id(original_thought.source_task_id)
                    if original_task:
                        persistence.update_task_status(original_task.task_id, TaskStatus.ACTIVE)
                        logger.info(f"Reactivated task {original_task.task_id} due to guidance")
                        
                        # Extract deferral reason from the original thought's final_action
                        deferral_reason = "Unknown deferral reason"
                        if original_thought.final_action and isinstance(original_thought.final_action, dict):
                            action_params = original_thought.final_action.get('action_parameters', {})
                            if isinstance(action_params, dict) and 'reason' in action_params:
                                deferral_reason = action_params['reason']
                        
                        # Create a new thought with PROCESSING status that includes original content + deferral reason + WA response
                        # Reset round_number to 0 to give fresh rounds after deferral
                        # Create guidance context by copying original context and adding guidance data
                        if original_thought.context:
                            guidance_context = original_thought.context.model_copy(update={
                                "guidance_message_id": msg.message_id,
                                "guidance_author": msg.author_name,
                                "guidance_content": msg.content,
                                "is_guidance_response": True,
                                "original_round_number": original_thought.round_number,  # Store original for reference
                                "original_thought_id": referenced_thought_id,
                                "deferral_reason": deferral_reason
                            })
                        else:
                            from ciris_engine.schemas.context_schemas_v1 import ThoughtContext
                            guidance_context = ThoughtContext(
                                guidance_message_id=msg.message_id,
                                guidance_author=msg.author_name,
                                guidance_content=msg.content,
                                is_guidance_response=True,
                                original_round_number=original_thought.round_number,
                                original_thought_id=referenced_thought_id,
                                deferral_reason=deferral_reason
                            )
                        
                        # Combine content with WA response last to ensure it's acted upon
                        combined_content = f"ORIGINAL THOUGHT: {original_thought.content}\n\n" \
                                         f"DEFERRED WITH QUESTION FOR WA: {deferral_reason}\n\n" \
                                         f"WISE AUTHORITY RESPONSE: {msg.content}"
                        
                        guidance_thought = Thought(
                            thought_id=str(uuid.uuid4()),
                            source_task_id=original_task.task_id,
                            parent_thought_id=referenced_thought_id,
                            thought_type="guidance",
                            status=ThoughtStatus.PROCESSING,  # Set to PROCESSING status
                            created_at=datetime.now(timezone.utc).isoformat(),
                            updated_at=datetime.now(timezone.utc).isoformat(),
                            round_number=0,  # Reset to 0 for fresh processing after guidance
                            content=combined_content,
                            context=guidance_context
                        )
                        persistence.add_thought(guidance_thought)
                        logger.info(f"Created guidance thought {guidance_thought.thought_id} as child of deferred thought {referenced_thought_id}")
                        
                        # Send success confirmation
                        success_msg = f"✅ **Guidance Received**: Successfully processed guidance for thought `{referenced_thought_id}`\n" \
                                     f"📝 **Task**: Reactivated task `{original_task.task_id}`\n" \
                                     f"🧠 **New Thought**: Created guidance thought `{guidance_thought.thought_id}`\n" \
                                     f"🔄 **Status**: Ready for processing"
                        await self._send_deferral_message(success_msg)
                        return
            
            # If we get here, it's unsolicited guidance - create a new task
            task = Task(
                task_id=str(uuid.uuid4()),
                description=f"Guidance received from authorized WA {msg.author_name} (ID: {msg.author_id}) please act accordingly",
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
            logger.info(f"Created unsolicited guidance task {task.task_id} - seed thought will be generated automatically")
                
        except Exception as e:
            logger.error(f"Error processing guidance message {msg.message_id}: {e}", exc_info=True)

