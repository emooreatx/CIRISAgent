import logging
import os
import asyncio
import json # Added import for json.dumps
import re # Added import for regex
import ast # Added import for literal_eval
import uuid # Added import for uuid
from datetime import datetime, timezone # Added datetime imports
import discord # type: ignore
from typing import Dict, Any, Optional, List # Added List

from ciris_engine.utils import DEFAULT_WA

from pydantic import BaseModel, Field

from .base import Service
from ciris_engine.action_handlers.action_dispatcher import ActionDispatcher
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, ThoughtStatus
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.action_params_v1 import DeferParams, RejectParams, SpeakParams, ToolParams
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine import persistence  # For creating tasks and updating status
from .discord_event_queue import DiscordEventQueue
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.utils import extract_user_nick

logger = logging.getLogger(__name__)

DISCORD_MESSAGE_LIMIT = 2000

class DiscordConfig(BaseModel):
    bot_token_env_var: str = Field(default="DISCORD_BOT_TOKEN", description="Environment variable for the Discord bot token.")
    deferral_channel_id_env_var: str = Field(default="DISCORD_DEFERRAL_CHANNEL_ID", description="Environment variable for the deferral channel ID.")
    wa_user_id_env_var: str = Field(default="DISCORD_WA_USER_ID", description="Environment variable for the Wise Authority user ID for corrections.")
    monitored_channel_id_env_var: str = Field(default="DISCORD_CHANNEL_ID", description="Environment variable for a specific channel ID where all non-bot messages should be processed.")
    max_message_history: int = Field(default=2, description="Maximum number of messages to keep in history per conversation for LLM context.")
    
    # Loaded at runtime
    bot_token: Optional[str] = None
    deferral_channel_id: Optional[int] = None
    wa_user_id: Optional[str] = None
    monitored_channel_id: Optional[int] = None

    def load_env_vars(self):
        self.bot_token = os.getenv(self.bot_token_env_var)
        
        deferral_id_str = os.getenv(self.deferral_channel_id_env_var)
        if deferral_id_str and deferral_id_str.isdigit():
            self.deferral_channel_id = int(deferral_id_str)
            
        wa_user_id_str = os.getenv(self.wa_user_id_env_var, DEFAULT_WA)
        if wa_user_id_str and wa_user_id_str.isdigit():
            self.wa_user_id = wa_user_id_str
        else:
            self.wa_user_id = DEFAULT_WA
            
        monitored_channel_id_str = os.getenv(self.monitored_channel_id_env_var)
        if monitored_channel_id_str and monitored_channel_id_str.isdigit():
            self.monitored_channel_id = int(monitored_channel_id_str)

        if not self.bot_token:
            logger.error(f"Discord bot token not found in env var: {self.bot_token_env_var}")
            raise ValueError(f"Missing Discord bot token: {self.bot_token_env_var}")
        # Warnings for optional IDs
        if not self.deferral_channel_id:
            logger.warning(f"Discord deferral channel ID not found or invalid in env var: {self.deferral_channel_id_env_var}. Deferral reporting may fail.")
        if not self.wa_user_id:
            logger.warning(f"Discord WA User ID not found or invalid in env var: {self.wa_user_id_env_var}. WA corrections via DM may not work.")
        if not self.monitored_channel_id:
            logger.warning(f"Specific monitored channel ID not found or invalid in env var: {self.monitored_channel_id_env_var}. Bot will only respond to DMs and mentions.")


def _truncate_discord_message(message: str, limit: int = DISCORD_MESSAGE_LIMIT) -> str:
    """Truncates a message to fit within Discord's character limit."""
    if len(message) <= limit:
        return message
    return message[:limit-3] + "..."


class DiscordService(Service):
    def __init__(self, action_dispatcher: ActionDispatcher, config: Optional[DiscordConfig] = None,
                 event_queue: Optional[DiscordEventQueue[IncomingMessage]] = None):
        super().__init__(config.model_dump() if config else None)  # Pass config dict to parent
        self.action_dispatcher = action_dispatcher
        self.config = config or DiscordConfig()
        self.config.load_env_vars()  # Load token and IDs from environment
        logger.info(f"Loaded monitored_channel_id: {self.config.monitored_channel_id} (from env: {os.getenv('DISCORD_CHANNEL_ID')})")
        self.event_queue = event_queue or DiscordEventQueue[IncomingMessage]()

        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        intents.guilds = True # Needed for fetching guild, channels, members
        self.bot = discord.Client(intents=intents)

        self._register_discord_events()
        logger.info("DiscordService initialized.")

    async def fetch_new_messages(self) -> List[discord.Message]:
        """Fetches recent messages from the monitored channel."""
        if not self.config.monitored_channel_id:
            return []
        try:
            channel = self.bot.get_channel(self.config.monitored_channel_id) or await self.bot.fetch_channel(self.config.monitored_channel_id)
            messages = [m async for m in channel.history(limit=5)]
            return [m for m in messages if m.author != self.bot.user and not m.author.bot]
        except Exception as e:
            logger.error("Failed to fetch new messages: %s", e)
            return []

    def _register_discord_events(self):
        @self.bot.event
        async def on_ready():
            if not self.bot.user:
                logger.error("Discord bot user not found on_ready.")
                return
            logger.info(f"DiscordService: Logged in as {self.bot.user.name} ({self.bot.user.id})")

        @self.bot.event
        async def on_message(message: discord.Message):
            if message.author == self.bot.user or message.author.bot:
                return

            # --- Message Filtering ---
            # Process message if it's a DM, mentions the bot, OR is in the specifically monitored channel.
            is_dm = isinstance(message.channel, discord.DMChannel)
            is_monitored_channel = self.config.monitored_channel_id and message.channel.id == self.config.monitored_channel_id
            is_mention = self.bot.user and self.bot.user.mentioned_in(message) # Ensure self.bot.user is not None

            should_process = is_dm or is_mention or is_monitored_channel

            if not should_process:
                log_reason = f"Ignoring message {message.id} in channel {message.channel.id}: Not a DM, mention, or the monitored channel ({self.config.monitored_channel_id})."
                logger.debug(log_reason)
                return
            # --- End Message Filtering ---

            logger.info(f"DiscordService: Processing message {message.id} from {message.author.name} in {'DM' if is_dm else message.channel.name} (Monitored Channel: {is_monitored_channel}, Mention: {is_mention}). Content: {message.content[:50]}...")

            # This context will be stored with the Task and eventually passed to the ActionDispatcher
            # Ensure 'origin_service' is set here.
            task_initial_context = {
                "message_id": str(message.id),
                "channel_id": str(message.channel.id),
                "guild_id": str(message.guild.id) if message.guild else None,
                "author_id": str(message.author.id),
                "author_name": await extract_user_nick(message=message) or message.author.name,
                "content": message.content, # The raw message content
                "timestamp": message.created_at.isoformat(),
                "origin_service": "discord", # Crucial for ActionDispatcher routing
                # Add any other relevant Discord message attributes if needed later
            }

            # --- WA Correction Handling (Reply in Deferral Channel) ---
            if message.reference and self.config.deferral_channel_id and message.channel.id == self.config.deferral_channel_id:
                logger.info(
                    f"Potential WA correction via reply in deferral channel {message.channel.id} by {message.author.name}."
                )

                original_task_id = None
                corrected_thought_id = None
                
                # Attempt to retrieve the referenced deferral report message
                referenced_message: Optional[discord.Message] = None
                if message.reference.resolved and isinstance(message.reference.resolved, discord.Message):
                    referenced_message = message.reference.resolved
                elif message.reference.message_id:
                    try:
                        referenced_message = await message.channel.fetch_message(message.reference.message_id)
                    except Exception as e:
                        logger.warning(
                            f"Could not fetch referenced message {message.reference.message_id}: {e}"
                        )

                deferral_data = None

                if referenced_message:
                    replied_to_content = referenced_message.content
                    deferral_json_match = re.search(r"```json\n(.*)\n```", replied_to_content, re.DOTALL)
                    if deferral_json_match:
                        try:
                            deferral_data = json.loads(deferral_json_match.group(1))
                        except Exception as e:
                            logger.warning(f"Failed to parse deferral package JSON: {e}")

                if message.reference and message.reference.message_id:
                    mapping = persistence.get_deferral_report_context(str(message.reference.message_id))
                    if mapping:
                        original_task_id, corrected_thought_id, _ = mapping
                        logger.info(
                            "Retrieved deferral mapping for message %s -> task %s, thought %s",
                            message.reference.message_id,
                            original_task_id,
                            corrected_thought_id,
                        )
                    elif referenced_message:
                        replied_to_content = referenced_message.content
                        task_id_match = re.search(r"Task ID:\s*`([^`]+)`", replied_to_content)
                        thought_id_match = re.search(r"Deferred Thought ID:\s*`([^`]+)`", replied_to_content)
                        if task_id_match:
                            original_task_id = task_id_match.group(1)
                        if thought_id_match:
                            corrected_thought_id = thought_id_match.group(1)
                        logger.debug("Fallback regex extraction: task=%s thought=%s", original_task_id, corrected_thought_id)
                    else:
                        logger.warning("WA correction reply reference could not be resolved or fetched.")

                if original_task_id:
                    try:
                        await message.add_reaction("✅")
                    except Exception as e:
                        logger.exception(
                            f"DiscordService: Failed to add reaction for task {original_task_id}: {e}"
                        )
                        await message.add_reaction("❌")
                else:
                    logger.error("Cannot process correction: Original Task ID not found in deferral report.")
                    await message.add_reaction("❓")
                
                return # Stop further processing, as this was a correction

            # --- Regular Message Handling (Enqueue Event) ---
            logger.info(f"Enqueuing message {message.id} from {message.author.name} for observer.")
            incoming = IncomingMessage(
                message_id=str(message.id),
                author_id=str(message.author.id),
                author_name=await extract_user_nick(message=message) or message.author.name,
                content=message.content,
                channel_id=str(message.channel.id),
                reference_message_id=str(message.reference.message_id) if message.reference and message.reference.message_id else None,
                timestamp=message.created_at.isoformat() if message.created_at else None,
                is_bot=message.author.bot,
                is_dm=isinstance(message.channel, discord.DMChannel),
            )
            setattr(incoming, "_raw_message", message)
            try:
                self.event_queue.enqueue_nowait(incoming)
                logger.debug(
                    "DiscordService: Enqueued message %s for observer queue.",
                    message.id,
                )
            except asyncio.QueueFull:
                logger.warning(
                    "Event queue full; dropping message %s", message.id
                )
            except Exception as e:
                logger.exception(
                    "DiscordService: Failed to enqueue event for message %s: %s",
                    message.id,
                    e,
                )


    async def _handle_discord_action(self, result: ActionSelectionResult, dispatch_context: Dict[str, Any]):
        logger.debug(f"DiscordService handling action: {result.selected_handler_action.value} with context: {dispatch_context}")
        
        # dispatch_context contains 'thought_id', 'source_task_id', 'origin_service',
        # and the context associated with the *source task* (retrieved by AgentProcessor).
        # This context should contain the original user's message details.
        
        thought_id = dispatch_context.get("thought_id")
        
        # Get target channel/message from the dispatch_context (which comes from the task)
        target_channel_id_str = dispatch_context.get("channel_id")
        target_message_id_str = dispatch_context.get("message_id") # This is the ID of the message that created the task

        if not target_channel_id_str:
            logger.error("DiscordService: Target 'channel_id' not found in dispatch_context. Cannot execute action.")
            return

        # Fetch the target channel
        try:
            target_channel_id = int(target_channel_id_str)
            target_channel = self.bot.get_channel(target_channel_id) or await self.bot.fetch_channel(target_channel_id)
            if not isinstance(target_channel, (discord.TextChannel, discord.DMChannel, discord.Thread)):
                logger.error(f"DiscordService: Target channel {target_channel_id} is not a valid text-based channel. Type: {type(target_channel)}")
                return
        except (ValueError, discord.NotFound, discord.Forbidden) as e:
            logger.error(f"DiscordService: Error fetching target channel {target_channel_id_str}: {e}")
            return
        except Exception as e:
             logger.exception(f"DiscordService: Unexpected error fetching target channel {target_channel_id_str}: {e}")
             return

        action_type = result.selected_handler_action
        params = result.action_parameters

        try:
            if action_type == HandlerActionType.SPEAK:
                if isinstance(params, SpeakParams):
                    content_to_send = _truncate_discord_message(params.content)
                    sent_message: Optional[discord.Message] = None # To store the message object the bot sends

                    if target_message_id_str:
                        try:
                            target_message_id = int(target_message_id_str)
                            # Fetch the message we intend to reply to (original user's message)
                            message_to_reply_to = await target_channel.fetch_message(target_message_id)
                            sent_message = await message_to_reply_to.reply(content_to_send) # Capture sent message
                            logger.info(f"DiscordService: Replied to message {target_message_id} in channel {target_channel_id}.")
                        except (ValueError, discord.NotFound, discord.Forbidden) as e:
                            logger.error(f"DiscordService: Error fetching message {target_message_id_str} in channel {target_channel_id} to reply: {e}. Sending to channel instead.")
                            sent_message = await target_channel.send(content_to_send) # Capture sent message (Fallback)
                        except Exception as e:
                            logger.exception(f"DiscordService: Unexpected error replying to message {target_message_id_str} in channel {target_channel_id}: {e}. Sending to channel instead.")
                            sent_message = await target_channel.send(content_to_send) # Capture sent message (Fallback)
                    else:
                        # If there's no target message ID (e.g., task initiated differently), just send to the channel
                        logger.warning(f"DiscordService: Target 'message_id' not found in dispatch_context. Sending SPEAK to channel {target_channel_id} instead of replying.")
                        sent_message = await target_channel.send(content_to_send) # Capture sent message
                else:
                    logger.error(f"DiscordService: Invalid params type for SPEAK: {type(params)}")

            elif action_type == HandlerActionType.DEFER:
                if isinstance(params, DeferParams):
                    user_message_content = _truncate_discord_message(f"This requires further review (Reason: {params.reason}). It has been logged for wisdom-based deferral.")
                    # DEFER notification should always go back to the message that triggered the deferral
                    if target_message_id_str:
                        try:
                            target_message_id = int(target_message_id_str)
                            message_to_reply_to = await target_channel.fetch_message(target_message_id)
                            await message_to_reply_to.reply(user_message_content)
                            logger.info(f"DiscordService: Replied DEFER notification to message {target_message_id} in channel {target_channel_id}.")
                        except Exception as e:
                            logger.error(f"DiscordService: Error replying DEFER notification to message {target_message_id_str}: {e}. Sending to channel instead.")
                            await target_channel.send(user_message_content) # Fallback
                    else:
                        logger.warning(f"DiscordService: Target 'message_id' not found in dispatch_context for DEFER. Sending notification to channel {target_channel_id} instead of replying.")
                        await target_channel.send(user_message_content)
                    
                    if self.config.deferral_channel_id:
                        logger.debug(f"DiscordService: deferral_channel_id={self.config.deferral_channel_id}")
                        deferral_channel = self.bot.get_channel(self.config.deferral_channel_id) or await self.bot.fetch_channel(self.config.deferral_channel_id)
                        if deferral_channel and isinstance(deferral_channel, discord.TextChannel):
                            source_task_id = dispatch_context.get("source_task_id", "Unknown")
                            deferred_thought_id = thought_id or "Unknown"

                            package = params.deferral_package_content or {}
                            if "metadata" in package and "user_nick" in package:
                                deferral_report = (
                                    f"**Memory Deferral Report**\n"
                                    f"**Task ID:** `{source_task_id}`\n"
                                    f"**Deferred Thought ID:** `{deferred_thought_id}`\n"
                                    f"**User:** {package.get('user_nick')} Channel: {package.get('channel')}\n"
                                    f"**Reason:** {params.reason}\n"
                                    f"**Metadata:** ```json\n{json.dumps(package.get('metadata'), indent=2)}\n```"
                                )
                            else:
                                deferral_report = (
                                    f"**Deferral Report**\n"
                                    f"**Task ID:** `{source_task_id}`\n"
                                    f"**Deferred Thought ID:** `{deferred_thought_id}`\n"
                                    f"**Reason:** {params.reason}\n"
                                    f"**Original Context:** `{str(dispatch_context)[:800]}`\n"
                                    f"**Deferral Package:** ```json\n{json.dumps(package, indent=2)}\n```"
                                )
                            try:
                                sent_report = await deferral_channel.send(_truncate_discord_message(deferral_report))
                                logger.info(
                                    f"DiscordService: Sent DEFER report for task {source_task_id}, thought {deferred_thought_id} to deferral channel {self.config.deferral_channel_id} as message {sent_report.id}."
                                )
                                persistence.save_deferral_report_mapping(
                                    str(sent_report.id),
                                    source_task_id,
                                    deferred_thought_id,
                                    package,
                                )
                            except Exception as send_exc:
                                logger.error(
                                    f"DiscordService: Failed to send DEFER report to channel {self.config.deferral_channel_id}: {send_exc}"
                                )
                        else:
                            logger.error(f"DiscordService: Could not find or access deferral channel {self.config.deferral_channel_id}.")
                    else:
                        logger.warning("DiscordService: Deferral channel ID not configured. Cannot send deferral report.")
                    # Update thought status in persistence
                    if thought_id:
                        persistence.update_thought_status(
                            thought_id=thought_id,
                            new_status=ThoughtStatus.DEFERRED, # Mark thought as deferred
                            # final_action_result could store deferral details if needed
                            final_action_result=result.model_dump() 
                        )
                        logger.info(f"DiscordService: Marked thought {thought_id} as DEFERRED.")
                    # Task status (e.g., PAUSED) might be handled by AgentProcessor or a dedicated task manager
                else:
                    logger.error(f"DiscordService: Invalid params type for DEFER: {type(params)}") # Corrected log

            elif action_type == HandlerActionType.REJECT: # Corrected from REJECT_THOUGHT
                if isinstance(params, RejectParams):
                    rejection_message = _truncate_discord_message(f"Unable to proceed with this request. Reason: {params.reason}")
                    # Send rejection to the target channel, potentially as a reply if target_message_id_str exists
                    if target_message_id_str:
                         try:
                             target_message_id = int(target_message_id_str)
                             message_to_reply_to = await target_channel.fetch_message(target_message_id)
                             await message_to_reply_to.reply(rejection_message)
                         except Exception: # Fallback if reply fails
                             await target_channel.send(rejection_message)
                    else:
                         await target_channel.send(rejection_message)
                    logger.info(f"DiscordService: Sent REJECT message to channel {target_channel_id}.")
                    if thought_id:
                        persistence.update_thought_status(thought_id, ThoughtStatus.COMPLETED, final_action_result=result.model_dump()) # Or FAILED
                else:
                    logger.error(f"DiscordService: Invalid params type for REJECT: {type(params)}") # Corrected log
            
            elif action_type == HandlerActionType.TOOL:
                if isinstance(params, ToolParams):
                    tool_name = params.tool_name
                    tool_args = params.arguments
                    logger.info(f"DiscordService: Received USE_TOOL action: {tool_name} with args {tool_args}.")
                    # Implement Discord-specific moderation tools here
                    if tool_name == "discord_delete_message":
                        # Use the target_message_id_str from the task context by default
                        msg_id_to_delete_str = tool_args.get("message_id", target_message_id_str)
                        if msg_id_to_delete_str:
                            try:
                                msg_id_to_delete = int(msg_id_to_delete_str)
                                msg_to_delete = await target_channel.fetch_message(msg_id_to_delete)
                                await msg_to_delete.delete()
                                logger.info(f"DiscordService: Deleted message {msg_id_to_delete} in channel {target_channel_id}.")
                                await target_channel.send(f"Moderation: Message {msg_id_to_delete} deleted.", delete_after=10)
                            except Exception as e_mod:
                                logger.error(f"DiscordService: Error deleting message {msg_id_to_delete_str}: {e_mod}")
                                await target_channel.send(f"Moderation: Failed to delete message {msg_id_to_delete_str}.", delete_after=10)
                        else:
                            logger.warning(f"DiscordService: USE_TOOL 'discord_delete_message' called without 'message_id' in arguments or task context.")
                    # Add other moderation tools like ban_user, kick_user, etc.
                    else:
                        await target_channel.send(f"Action '{tool_name}' acknowledged (Discord implementation pending).")
                    if thought_id:
                        persistence.update_thought_status(thought_id, ThoughtStatus.COMPLETED, final_action_result=result.model_dump())
                else:
                    logger.error(f"DiscordService: Invalid params type for USE_TOOL: {type(params)}")

            else:
                logger.debug(f"DiscordService: No specific Discord handler for action type {action_type.value}")
                # For actions not handled by DiscordService (e.g., MEMORIZE, REMEMBER, OBSERVE),
                # ensure their status is appropriately updated if they are terminal for the thought.
                if thought_id and action_type not in [HandlerActionType.PONDER]: # PONDER is handled by WC
                    persistence.update_thought_status(thought_id, ThoughtStatus.COMPLETED, final_action_result=result.model_dump())


        except discord.HTTPException as e:
            logger.error(f"DiscordService: Discord API error during action '{action_type.value}': {e.status} {e.text}")
            if thought_id:
                persistence.update_thought_status(thought_id, ThoughtStatus.FAILED, final_action_result={"error": f"Discord API Error: {e.text}"})
        except Exception as e:
            logger.exception(f"DiscordService: Unexpected error handling action '{action_type.value}': {e}")
            if thought_id:
                persistence.update_thought_status(thought_id, ThoughtStatus.FAILED, final_action_result={"error": f"Handler Exception: {str(e)}"})


    async def start(self):
        if not self.config.bot_token:
            logger.critical("DiscordService: Bot token is not configured. Cannot start.")
            return
        try:
            logger.info("DiscordService: Starting bot...")
            await self.bot.start(self.config.bot_token)
        except Exception as e:
            logger.exception(f"DiscordService: Error during bot start: {e}")

    async def stop(self):
        logger.info("DiscordService: Stopping bot...")
        await self.bot.close()
        logger.info("DiscordService: Bot stopped.")
