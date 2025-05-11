import logging
import json
import discord # type: ignore
from typing import Dict, Any, Union

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
    message_content: str
) -> None:
    """
    Sends a message as a reply to the original Discord message.
    Can accept either a discord.Message object or a dict with 'id' and 'channel_id'.

    Args:
        discord_client: The active discord.Client instance.
        original_message_input: The discord.Message object to reply to, or a dict
                                containing 'id' and 'channel_id' of the message.
        message_content: The string content to send.
    """
    if not message_content:
        logger.warning("handle_discord_speak called with empty message_content. No message sent.")
        return

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
            except discord.HTTPException as e:
                logger.error(f"Discord API error while fetching original message {message_id_str} from channel {channel_id_str} for speak action: {e.status} {e.text}")
            except Exception as e:
                logger.error(f"Unexpected error fetching original message {message_id_str} from channel {channel_id_str} for speak action: {e}", exc_info=True)
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

    # Use resolved_original_message from here onwards
    original_message = resolved_original_message

    try:
        truncated_reply = _truncate_discord_message(message_content)
        await original_message.reply(truncated_reply)
        logger.info(f"Sent speak reply to channel {original_message.channel.id} for message {original_message.id}: {truncated_reply[:100]}...")
    except discord.errors.HTTPException as e:
        logger.error(f"Discord HTTP Error sending speak reply to channel {original_message.channel.id}: {e.status} - {e.text}")
    except Exception as e:
        logger.error(f"An unexpected error occurred in handle_discord_speak: {e}", exc_info=True)

async def handle_discord_deferral(
    discord_client: discord.Client,
    original_message_input: Union[discord.Message, Dict[str, Any]],
    action_params: Dict[str, Any],
    deferral_channel_id_str: str
) -> None:
    """
    Handles deferral of a thought/action on Discord.
    It notifies the user who sent the original message and sends a detailed report
    to a specified deferral channel.

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
            except discord.HTTPException as e:
                logger.error(f"Discord API error while fetching original message {message_id_str} from channel {channel_id_str} for deferral: {e.status} {e.text}")
            except Exception as e:
                logger.error(f"Unexpected error fetching original message {message_id_str} from channel {channel_id_str} for deferral: {e}", exc_info=True)
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
        if deferral_channel_id_str:
            try:
                deferral_channel_id = int(deferral_channel_id_str)
                deferral_channel = discord_client.get_channel(deferral_channel_id)
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
    except discord.errors.HTTPException as e:
        logger.error(f"Discord HTTP Error sending user deferral notification to {original_message.channel.id}: {e.status} - {e.text}")
    except Exception as e:
        logger.error(f"An unexpected error occurred sending user deferral notification: {e}", exc_info=True)

    try:
        deferral_channel_id = int(deferral_channel_id_str)
        deferral_channel = discord_client.get_channel(deferral_channel_id)

        if not deferral_channel:
            logger.error(f"Deferral channel with ID {deferral_channel_id_str} not found by client. Detailed deferral message not sent.")
            return
        if not isinstance(deferral_channel, discord.TextChannel):
            logger.error(f"Deferral channel {deferral_channel_id_str} is not a TextChannel. Detailed deferral message not sent.")
            return

        details = (
            f"**CIRIS Engine Deferral Report**\n\n"
            f"**Original Message ID:** `{original_message.id}`\n"
            f"**User:** {original_message.author.mention} (`{original_message.author.name}#{original_message.author.discriminator}` - ID: `{original_message.author.id}`)\n"
            f"**Channel:** {original_message.channel.mention if isinstance(original_message.channel, discord.TextChannel) else f'DM with {original_message.author.name}'} (ID: `{original_message.channel.id}`)\n"
            f"**Original Message Content:**\n```\n{original_message.content}\n```\n\n"
            f"**Reason for Deferral (from ActionSelectionPDMA):**\n```\n{reason_for_deferral}\n```\n"
        )
        if guardrail_failure_reason and guardrail_failure_reason != reason_for_deferral:
             details += f"**Guardrail Failure Specifics:**\n```\n{guardrail_failure_reason}\n```\n"

        if original_proposed_action != "N/A":
            details += f"**Originally Proposed Agent Action:** `{original_proposed_action}`\n"
            if original_action_parameters:
                 details += f"**Original Action Parameters:**\n```json\n{json.dumps(original_action_parameters, indent=2)}\n```\n"
        
        if epistemic_data:
            details += f"\n**Epistemic Data (if available from guardrail):**\n"
            entropy_val = epistemic_data.get('entropy')
            coherence_val = epistemic_data.get('coherence')
            epistemic_error = epistemic_data.get('error')

            details += f"  - Entropy: {entropy_val:.4f if isinstance(entropy_val, float) else 'N/A'}\n"
            details += f"  - Coherence: {coherence_val:.4f if isinstance(coherence_val, float) else 'N/A'}\n"
            if epistemic_error:
                details += f"  - Epistemic Check Error: {epistemic_error}\n"
        
        details += f"\nMessage Link: {original_message.jump_url}"

        await deferral_channel.send(_truncate_discord_message(details))
        logger.info(f"Sent detailed deferral report to review channel #{deferral_channel.name} ({deferral_channel.id}).")

    except ValueError:
        logger.error(f"Invalid deferral_channel_id: '{deferral_channel_id_str}'. Must be an integer.")
    except discord.errors.HTTPException as e:
        logger.error(f"Discord HTTP Error sending detailed deferral message to review channel: {e.status} - {e.text}")
    except Exception as e:
        logger.error(f"An unexpected error occurred sending detailed deferral message to review channel: {e}", exc_info=True)
