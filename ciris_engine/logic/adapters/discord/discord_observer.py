import logging
import asyncio
from typing import List, Optional, Any

from ciris_engine.schemas.runtime.models import ThoughtType
from ciris_engine.schemas.runtime.messages import DiscordMessage
from ciris_engine.schemas.runtime.system_context import SystemSnapshot, ChannelContext
from ciris_engine.schemas.runtime.models import TaskContext
from ciris_engine.schemas.runtime.processing_context import ThoughtContext
from ciris_engine.logic.utils.channel_utils import create_channel_context
from ciris_engine.logic.buses import BusManager
from ciris_engine.logic.secrets.service import SecretsService
from ciris_engine.logic.adapters.base_observer import BaseObserver
from ciris_engine.logic.adapters.discord.discord_vision_helper import DiscordVisionHelper
from datetime import datetime, timezone

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
        monitored_channel_ids: Optional[List[str]] = None,
        deferral_channel_id: Optional[str] = None,
        wa_user_ids: Optional[List[str]] = None,
        memory_service: Optional[Any] = None,
        agent_id: Optional[str] = None,
        bus_manager: Optional[BusManager] = None,
        filter_service: Optional[Any] = None,
        secrets_service: Optional[SecretsService] = None,
        communication_service: Optional[Any] = None,
        time_service: Optional[Any] = None,
    ) -> None:
        super().__init__(
            on_observe=lambda _: asyncio.sleep(0),
            bus_manager=bus_manager,
            memory_service=memory_service,
            agent_id=agent_id,
            filter_service=filter_service,
            secrets_service=secrets_service,
            time_service=time_service,
            origin_service="discord",
        )
        self.communication_service = communication_service

        self.deferral_channel_id = deferral_channel_id
        self.wa_user_ids = wa_user_ids or []

        self.monitored_channel_ids = monitored_channel_ids or []
        
        # Log configuration for debugging
        logger.info(f"DiscordObserver initialized with:")
        logger.info(f"  - Monitored channels: {self.monitored_channel_ids}")
        logger.info(f"  - Deferral channel: {self.deferral_channel_id}")
        logger.info(f"  - WA user IDs: {self.wa_user_ids}")
        
        # Initialize vision helper
        self._vision_helper = DiscordVisionHelper()
        if self._vision_helper.is_available():
            logger.info("Discord Vision Helper initialized - image processing enabled")
        else:
            logger.warning("Discord Vision Helper not available - set CIRIS_OPENAI_VISION_KEY to enable")

    async def _send_deferral_message(self, content: str) -> None:
        """Send a message to the deferral channel."""
        if not self.communication_service:
            logger.warning("No communication service available to send deferral message")
            return
        
        if not self.deferral_channel_id:
            logger.warning("No deferral channel configured")
            return
        
        try:
            await self.communication_service.send_message(self.deferral_channel_id, content)
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
            logger.warning("DiscordObserver received non-DiscordMessage")  # type: ignore[unreachable]
            return
        # Check if message is from a monitored channel or deferral channel
        is_from_monitored = (self.monitored_channel_ids and msg.channel_id in self.monitored_channel_ids)
        is_from_deferral = (self.deferral_channel_id and msg.channel_id == self.deferral_channel_id)
        
        logger.info(f"Message from {msg.author_name} (ID: {msg.author_id}) in channel {msg.channel_id}")
        logger.info(f"  - Is from monitored channel: {is_from_monitored}")
        logger.info(f"  - Is from deferral channel: {is_from_deferral}")
        logger.info(f"  - Deferral channel ID: {self.deferral_channel_id}")
        
        if not (is_from_monitored or is_from_deferral):
            logger.debug("Ignoring message from channel %s (not in monitored channels %s or deferral %s)", 
                        msg.channel_id, self.monitored_channel_ids, self.deferral_channel_id)
            return
        
        # Check if this is the agent's own message
        is_agent_message = self.agent_id and msg.author_id == self.agent_id
        
        # Process message for secrets detection and replacement (for all messages)
        processed_msg = await self._process_message_secrets(msg)
        
        # Process any images in the message if vision is available
        if self._vision_helper.is_available() and hasattr(msg, 'raw_message') and msg.raw_message:
            try:
                # Process attachments
                image_descriptions = await self._vision_helper.process_message_images(msg.raw_message)
                
                # Process embeds if any
                embed_descriptions = None
                if hasattr(msg.raw_message, 'embeds') and msg.raw_message.embeds:
                    embed_descriptions = await self._vision_helper.process_embeds(msg.raw_message.embeds)
                
                # Append descriptions to the message content
                if image_descriptions or embed_descriptions:
                    additional_content = "\n\n[Image Analysis]\n"
                    if image_descriptions:
                        additional_content += image_descriptions
                    if embed_descriptions:
                        if image_descriptions:
                            additional_content += "\n\n"
                        additional_content += embed_descriptions
                    
                    # Create a new message with the augmented content
                    processed_msg = DiscordMessage(
                        message_id=processed_msg.message_id,
                        content=processed_msg.content + additional_content,
                        author_id=processed_msg.author_id,
                        author_name=processed_msg.author_name,
                        channel_id=processed_msg.channel_id,
                        is_bot=processed_msg.is_bot,
                        is_dm=processed_msg.is_dm,
                        raw_message=processed_msg.raw_message
                    )
                    
                    logger.info(f"Processed images in message {msg.message_id} from {msg.author_name}")
                    
            except Exception as e:
                logger.error(f"Failed to process images in message {msg.message_id}: {e}")
        
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
        # Store filter info in a way that doesn't modify the message object
        setattr(processed_msg, '_filter_priority', filter_result.priority)
        setattr(processed_msg, '_filter_context', filter_result.context_hints)
        setattr(processed_msg, '_filter_reasoning', filter_result.reasoning)
        
        # Process based on priority
        if filter_result.priority.value in ['critical', 'high']:
            # Immediate processing for high-priority messages
            logger.info(f"Processing {filter_result.priority.value} priority message {msg.message_id}: {filter_result.reasoning}")
            await self._handle_priority_observation(processed_msg, filter_result)
        else:
            # Normal processing for medium/low priority
            await self._handle_passive_observation(processed_msg)
            
        await self._recall_context(processed_msg)

    async def _handle_priority_observation(self, msg: DiscordMessage, filter_result: Any) -> None:
        """Handle high-priority messages with immediate processing"""
        from ciris_engine.logic.utils.constants import (
            DEFAULT_WA,
        )

        monitored_channel_ids = self.monitored_channel_ids or []
        wa_discord_user = DEFAULT_WA
        
        if msg.channel_id in monitored_channel_ids:
            await self._create_priority_observation_result(msg, filter_result)
        elif msg.channel_id == self.deferral_channel_id and (msg.author_id in self.wa_user_ids or msg.author_name == wa_discord_user):
            logger.info(f"[PRIORITY] Routing message to WA feedback queue - author {msg.author_name} is WA")
            await self._add_to_feedback_queue(msg)
        else:
            logger.info(f"[PRIORITY] Not routing to WA feedback - checking conditions:")
            logger.info(f"  - Is deferral channel: {msg.channel_id == self.deferral_channel_id}")
            logger.info(f"  - Author ID in WA list: {msg.author_id in self.wa_user_ids}")
            logger.info(f"  - Author name matches DEFAULT_WA '{wa_discord_user}': {msg.author_name == wa_discord_user}")
            logger.debug("Ignoring priority message from channel %s, author %s (ID: %s)", msg.channel_id, msg.author_name, msg.author_id)

    def _create_task_context_with_extras(self, msg: DiscordMessage, extras: dict) -> TaskContext:
        """Create a TaskContext with extra fields."""
        # TaskContext only has these fields, extras are ignored
        # This is fine since extras were meant for ThoughtContext
        return TaskContext(
            channel_id=msg.channel_id,
            user_id=msg.author_id,
            correlation_id=msg.message_id,
            parent_task_id=None
        )

    async def _handle_passive_observation(self, msg: DiscordMessage) -> None:
        from ciris_engine.logic.utils.constants import (
            DEFAULT_WA,
        )

        monitored_channel_ids = self.monitored_channel_ids or []
        wa_discord_user = DEFAULT_WA
        
        if msg.channel_id in monitored_channel_ids:
            await self._create_passive_observation_result(msg)
        elif msg.channel_id == self.deferral_channel_id and (msg.author_id in self.wa_user_ids or msg.author_name == wa_discord_user):
            logger.info(f"Routing message to WA feedback queue - author {msg.author_name} is WA")
            await self._add_to_feedback_queue(msg)
        else:
            logger.info(f"Not routing to WA feedback - checking conditions:")
            logger.info(f"  - Is deferral channel: {msg.channel_id == self.deferral_channel_id}")
            logger.info(f"  - Author ID in WA list: {msg.author_id in self.wa_user_ids}")
            logger.info(f"  - Author name matches DEFAULT_WA '{wa_discord_user}': {msg.author_name == wa_discord_user}")
            logger.debug("Ignoring message from channel %s, author %s (ID: %s)", msg.channel_id, msg.author_name, msg.author_id)

    async def _add_to_feedback_queue(self, msg: DiscordMessage) -> None:
        """Process guidance/feedback from WA in deferral channel."""
        try:
            # First validate that the user is a wise authority
            from ciris_engine.logic.utils.constants import DEFAULT_WA
            wa_discord_user = DEFAULT_WA
            
            is_wise_authority = (msg.author_id in self.wa_user_ids or msg.author_name == wa_discord_user)
            
            if not is_wise_authority:
                error_msg = f"🚫 **Not Authorized**: User `{msg.author_name}` (ID: `{msg.author_id}`) is not a Wise Authority. Not proceeding with guidance processing."
                logger.warning(f"Non-WA user {msg.author_name} ({msg.author_id}) attempted to provide guidance")
                await self._send_deferral_message(error_msg)
                return
            from datetime import datetime, timezone
            import uuid
            import re
            from ciris_engine.schemas.runtime.models import Task, Thought
            from ciris_engine.schemas.runtime.enums import TaskStatus, ThoughtStatus
            from ciris_engine.logic import persistence

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
                        thought_id_pattern = r'Thought ID:\s*([a-zA-Z0-9_-]+)'
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
                thought_id_pattern = r'(?:thought\s+id|thought_id|re:\s*thought)[\s:]*([a-zA-Z0-9_-]+)'
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
                        persistence.update_task_status(original_task.task_id, TaskStatus.ACTIVE, self.time_service)
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
                            from ciris_engine.schemas.runtime.system_context import ThoughtContext, SystemSnapshot, UserProfile, TaskSummary
                            # Create channel context for guidance
                            guidance_channel_context = create_channel_context(
                                channel_id=msg.channel_id,
                                channel_type="discord",
                                is_deferral=True
                            )
                            # Create a minimal valid ThoughtContext
                            guidance_context = ThoughtContext(
                                system_snapshot=SystemSnapshot(
                                    channel_context=guidance_channel_context
                                ),
                                user_profiles={},
                                task_history=[]
                            )
                            # Add extra fields after creation
                            setattr(guidance_context, 'guidance_message_id', msg.message_id)
                            setattr(guidance_context, 'guidance_author', msg.author_name)
                            setattr(guidance_context, 'guidance_content', msg.content)
                            setattr(guidance_context, 'is_guidance_response', True)
                            setattr(guidance_context, 'original_round_number', original_thought.round_number)
                            setattr(guidance_context, 'original_thought_id', referenced_thought_id)
                            setattr(guidance_context, 'deferral_reason', deferral_reason)
                        
                        # Combine content with WA response last to ensure it's acted upon
                        combined_content = f"ORIGINAL THOUGHT: {original_thought.content}\n\n" \
                                         f"DEFERRED WITH QUESTION FOR WA: {deferral_reason}\n\n" \
                                         f"WISE AUTHORITY RESPONSE: {msg.content}"
                        
                        guidance_thought = Thought(
                            thought_id=str(uuid.uuid4()),
                            source_task_id=original_task.task_id,
                            parent_thought_id=referenced_thought_id,
                            thought_type=ThoughtType.GUIDANCE,
                            status=ThoughtStatus.PROCESSING,  # Set to PROCESSING status
                            created_at=self.time_service.now_iso() if self.time_service else datetime.now(timezone.utc).isoformat(),
                            updated_at=self.time_service.now_iso() if self.time_service else datetime.now(timezone.utc).isoformat(),
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
                channel_id=msg.channel_id,
                description=f"Guidance received from authorized WA {msg.author_name} (ID: {msg.author_id}) please act accordingly",
                status=TaskStatus.PENDING,
                priority=8,  # High priority for guidance
                created_at=self.time_service.now_iso() if self.time_service else datetime.now(timezone.utc).isoformat(),
                updated_at=self.time_service.now_iso() if self.time_service else datetime.now(timezone.utc).isoformat(),
                context=self._create_task_context_with_extras(
                    msg,
                    {
                        "message_id": msg.message_id,
                        "observation_type": "unsolicited_guidance",
                        "is_guidance": True,
                        "guidance_content": msg.content
                    }
                )
            )
            persistence.add_task(task)
            logger.info(f"Created unsolicited guidance task {task.task_id} - seed thought will be generated automatically")
                
        except Exception as e:
            logger.error(f"Error processing guidance message {msg.message_id}: {e}", exc_info=True)

