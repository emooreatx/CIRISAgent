import logging
import json
import discord # type: ignore
from typing import Dict, Any, Union
from ciris_engine.core.data_schemas import WBDPackage

logger = logging.getLogger(__name__)

DISCORD_MESSAGE_LIMIT = 2000

def _truncate_discord_message(message: str, limit: int = DISCORD_MESSAGE_LIMIT) -> str:
    """Truncates a message to fit within Discord's character limit."""
    if len(message) <= limit:
        return message
    # Leave space for ellipsis
    truncated = message[:limit-3] + "..."
    logger.info(f"Message truncated from {len(message)} to {len(truncated)} characters")
    return truncated

async def handle_discord_speak(
    discord_client: discord.Client,
    original_message_input: Union[discord.Message, Dict[str, Any]],
    action_params: Dict[str, Any],
) -> None:
    """
    Handles the SPEAK action by replying to the original Discord message.

    Args:
        discord_client: The active discord.Client instance.
        original_message_input: The original discord.Message object or a dict 
                                containing 'id' and 'channel_id' of the message.
        message_content: The text content to be spoken/replied by the bot.
    """
    resolved_original_message: discord.Message | None = None

    if isinstance(original_message_input, discord.Message):
        resolved_original_message = original_message_input
    elif isinstance(original_message_input, dict):
        message_id_str = original_message_input.get("id")
        channel_id_str = original_message_input.get("channel_id")

        if message_id_str and channel_id_str:
            try:
                message_id = int(message_id_str)
                channel_id = int(channel_id_str)
                
                channel = discord_client.get_channel(channel_id)
                if channel and isinstance(channel, (discord.TextChannel, discord.Thread, discord.DMChannel, discord.GroupChannel, discord.PartialMessageable)):
                    logger.info(f"Fetching original message {message_id} from channel {channel_id} for speak action.")
                    resolved_original_message = await channel.fetch_message(message_id)
                    logger.info(f"Successfully fetched original message {message_id} for speak action.")
                elif not channel:
                    logger.error(f"Could not find channel with ID: {channel_id} to fetch original message for speak action.")
                else:
                    logger.error(f"Channel with ID: {channel_id} (type: {type(channel)}) is not a messageable channel for speak action.")
            except discord.NotFound:
                logger.error(f"Original message with ID {message_id_str} not found in channel {channel_id_str} for speak action.")
            except discord.Forbidden:
                logger.error(f"Bot lacks permissions to fetch message {message_id_str} in channel {channel_id_str} for speak action.")
            except ValueError:
                logger.error(f"Invalid message_id ('{message_id_str}') or channel_id ('{channel_id_str}') format for speak action. Must be integers.")
            except discord.HTTPException as e_http:
                logger.error(f"Discord API error while fetching original message {message_id_str} from channel {channel_id_str} for speak action: {e_http.status} {e_http.text}")
            except Exception as e_generic:
                logger.error(f"Unexpected error fetching original message {message_id_str} from channel {channel_id_str} for speak action: {e_generic}", exc_info=True)
        else:
            missing_keys = []
            if not message_id_str: missing_keys.append("'id'")
            if not channel_id_str: missing_keys.append("'channel_id'")
            logger.error(
                f"Original message data (dict) for speak action is missing keys: {', '.join(missing_keys)}."
            )
    else:
        logger.error(
            f"Unsupported type for original_message_input: {type(original_message_input)} for speak action."
        )

    if not resolved_original_message:
        logger.error("Failed to resolve original message object for speak action. Cannot send reply.")
        return

    message_content = action_params.get("message_content") or action_params.get("message", "No message content provided.")
    try:
        truncated_reply = _truncate_discord_message(message_content)
        await resolved_original_message.reply(truncated_reply)
        logger.info(f"Sent speak reply to channel {resolved_original_message.channel.id} for message {resolved_original_message.id}: {truncated_reply[:100]}...")
    except discord.errors.HTTPException as e_http_reply:
        logger.error(f"Discord HTTP Error sending speak reply to channel {resolved_original_message.channel.id}: {e_http_reply.status} - {e_http_reply.text}")
    except Exception as e_generic_reply:
        logger.error(f"An unexpected error occurred in handle_discord_speak: {e_generic_reply}", exc_info=True)

from ciris_engine.core.thought_queue_manager import ThoughtQueueManager # Added import
from ciris_engine.core.data_schemas import ThoughtStatus # Added import

async def handle_discord_deferral(
    discord_client: discord.Client,
    thought_manager: ThoughtQueueManager, # Added
    current_thought_id: str, # Added
    current_task_id: str, # Added
    original_message_input: Union[discord.Message, Dict[str, Any]],
    action_params: Dict[str, Any],
    deferral_channel_id_str: str
) -> None:
    """
    Handles deferral of a thought/action on Discord.

    Args:
        discord_client: The active discord.Client instance.
        original_message_input: The original discord.Message object or a dict 
                                containing 'id' and 'channel_id' of the message.
        action_params: Parameters from ActionSelectionPDMAResult, typically containing
                       reasons for deferral and details of the proposed action.
        deferral_channel_id_str: The ID of the Discord channel to send deferral details to.
    """
    resolved_original_message: discord.Message | None = None

    if isinstance(original_message_input, discord.Message):
        resolved_original_message = original_message_input
    elif isinstance(original_message_input, dict):
        message_id_str = original_message_input.get("id")
        channel_id_str = original_message_input.get("channel_id")

        if message_id_str and channel_id_str:
            try:
                message_id = int(message_id_str)
                channel_id = int(channel_id_str)
                
                channel = discord_client.get_channel(channel_id)
                if channel and isinstance(channel, (discord.TextChannel, discord.Thread, discord.DMChannel, discord.GroupChannel, discord.PartialMessageable)):
                    logger.info(f"Fetching original message {message_id} from channel {channel_id} for deferral.")
                    resolved_original_message = await channel.fetch_message(message_id)
                    logger.info(f"Successfully fetched original message {message_id} for deferral.")
                elif not channel:
                    logger.error(f"Could not find channel with ID: {channel_id} to fetch original message for deferral.")
                else:
                    logger.error(f"Channel with ID: {channel_id} (type: {type(channel)}) is not a messageable channel for deferral.")
            except discord.NotFound:
                logger.error(f"Original message with ID {message_id_str} not found in channel {channel_id_str} for deferral.")
            except discord.Forbidden:
                logger.error(f"Bot lacks permissions to fetch message {message_id_str} in channel {channel_id_str} for deferral.")
            except ValueError:
                logger.error(f"Invalid message_id ('{message_id_str}') or channel_id ('{channel_id_str}') format for deferral. Must be integers.")
            except discord.HTTPException as e_http:
                logger.error(f"Discord API error while fetching original message {message_id_str} from channel {channel_id_str} for deferral: {e_http.status} {e_http.text}")
            except Exception as e_generic:
                logger.error(f"Unexpected error fetching original message {message_id_str} from channel {channel_id_str} for deferral: {e_generic}", exc_info=True)
        else:
            missing_keys = []
            if not message_id_str: missing_keys.append("'id'")
            if not channel_id_str: missing_keys.append("'channel_id'")
            logger.error(
                f"Original message data (dict) for deferral is missing keys: {', '.join(missing_keys)}."
            )
    else:
        logger.error(
            f"Unsupported type for original_message_input: {type(original_message_input)} for deferral."
        )

    if not resolved_original_message:
        logger.error(
            "Failed to resolve original message object for deferral. Cannot send deferral notifications."
        )
        # Optionally, send a message to the deferral channel if it's configured and the original message is the problem
        if deferral_channel_id_str and deferral_channel_id_str.isdigit(): # Check if it's a digit string
            try:
                deferral_channel_id_int = int(deferral_channel_id_str)
                deferral_channel = discord_client.get_channel(deferral_channel_id_int)
                if deferral_channel and isinstance(deferral_channel, discord.TextChannel):
                    await deferral_channel.send(
                        _truncate_discord_message(
                            f"**CIRIS Engine Deferral Report - ERROR**\n\n"
                            f"Failed to resolve the original Discord message for a deferral event. "
                            f"Input `original_message_input` was: `{str(original_message_input)[:500]}`. "
                            f"Action params: `{str(action_params)[:500]}`. "
                            f"The user who triggered this might not have been notified."
                        )
                    )
            except Exception as e_rc:
                logger.error(f"Failed to send message resolution failure notification to deferral channel: {e_rc}", exc_info=True)
        else:
            logger.error(f"Invalid or missing deferral_channel_id: '{deferral_channel_id_str}' for error reporting. Cannot send detailed deferral report.")
        return

    # Use resolved_original_message from here onwards
    original_message = resolved_original_message

    reason_for_deferral = action_params.get("reason", "Reason not specified by ActionSelectionPDMA.")
    original_proposed_action = action_params.get("original_proposed_action", "N/A")
    original_action_parameters = action_params.get("original_action_parameters", {})
    guardrail_failure_reason = action_params.get("guardrail_failure_reason", reason_for_deferral)
    epistemic_data = action_params.get("epistemic_data")

    user_deferral_message = "My current reasoning suggests this requires further review. This interaction will be logged for wisdom-based deferral."

    try:
        await original_message.reply(_truncate_discord_message(user_deferral_message))
        logger.info(f"Sent deferral notification to user {original_message.author.name} in channel {original_message.channel.id}.")
    except discord.errors.HTTPException as e_http_reply_user:
        logger.error(f"Discord HTTP Error sending user deferral notification to {original_message.channel.id}: {e_http_reply_user.status} - {e_http_reply_user.text}")
    except Exception as e_generic_reply_user:
        logger.error(f"An unexpected error occurred sending user deferral notification: {e_generic_reply_user}", exc_info=True)

    # Ensure deferral_channel_id_str is valid before attempting conversion and use
    if not deferral_channel_id_str or not deferral_channel_id_str.isdigit():
        logger.error(f"Invalid or missing deferral_channel_id: '{deferral_channel_id_str}'. This should not happen.")
        return

    try:
        deferral_channel_id_int = int(deferral_channel_id_str) 
        deferral_channel = discord_client.get_channel(deferral_channel_id_int)

        if not deferral_channel:
            logger.error(f"Deferral channel with ID {deferral_channel_id_str} not found by client. Detailed deferral message not sent.")
            return
        if not isinstance(deferral_channel, discord.TextChannel): # Ensure it's a TextChannel
            logger.error(f"Deferral channel {deferral_channel_id_str} (type: {type(deferral_channel)}) is not a TextChannel. Detailed deferral message not sent.")
            return

        # Construct WBDPackage
        pdma_trace_id = action_params.get("pdma_trace_id", "N/A")
        autonomy_tier = action_params.get("autonomy_tier", 0)
        context = action_params.get("context", "N/A")
        candidate_response = action_params.get("candidate_response", "N/A")
        metrics = action_params.get("metrics", {})
        trigger = action_params.get("trigger", "N/A")

        wbd_package = WBDPackage(
            pdma_trace_id=pdma_trace_id,
            autonomy_tier=autonomy_tier,
            context=context,
            candidate_response=candidate_response,
            metrics=metrics,
            trigger=trigger
        )

        details = wbd_package.model_dump_json(indent=2)

        await deferral_channel.send(_truncate_discord_message(details))
        logger.info(f"Sent detailed deferral report to review channel #{deferral_channel.name} ({deferral_channel.id}).")

        # Update the thought status to "deferred" and task status to "paused"
        if current_thought_id:
            try:
                # Update thought status to 'deferred'
                # Assuming round_processed and ponder_count might be relevant if available in action_params
                # For now, just setting status. The coordinator should have set these if it was a ponder-limit deferral.
                round_processed = action_params.get("round_processed") 
                ponder_count = action_params.get("ponder_count")

                thought_manager.update_thought_status(
                    thought_id=current_thought_id,
                    new_status=ThoughtStatus(status="deferred"),
                    round_processed=round_processed, # Pass if available
                    ponder_count=ponder_count # Pass if available
                )
                logger.info(f"Updated thought {current_thought_id} status to DEFERRED.")
            except Exception as e:
                logger.error(f"Failed to update thought {current_thought_id} status to DEFERRED: {e}", exc_info=True)
        else:
            logger.warning("current_thought_id not provided to handle_discord_deferral, cannot update thought status.")


        if current_task_id:
            try:
                from ciris_engine.core.data_schemas import TaskStatus
                thought_manager.update_task_status(current_task_id, TaskStatus(status="paused"))
                logger.info(f"Updated task {current_task_id} status to PAUSED after deferral.")
            except Exception as e:
                logger.error(f"Failed to update task {current_task_id} status to PAUSED: {e}", exc_info=True)
        else:
            logger.warning("current_task_id not provided to handle_discord_deferral, cannot update task status.")

    except ValueError:
        logger.error(f"Invalid deferral_channel_id after isdigit check: '{deferral_channel_id_str}'. This should not happen.")
    except discord.errors.HTTPException as e_http_defer:
        logger.error(f"Discord HTTP Error sending detailed deferral message to review channel: {e_http_defer.status} - {e_http_defer.text}")
    except Exception as e_generic_defer:
        logger.error(f"An unexpected error occurred sending detailed deferral message to review channel: {e_generic_defer}", exc_info=True)
