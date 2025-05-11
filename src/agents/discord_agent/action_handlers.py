import logging
import json
import discord # type: ignore
from typing import Dict, Any

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
    original_message: discord.Message,
    message_content: str
) -> None:
    """
    Sends a message as a reply to the original Discord message.

    Args:
        discord_client: The active discord.Client instance.
        original_message: The discord.Message object to reply to.
        message_content: The string content to send.
    """
    if not message_content:
        logger.warning("handle_discord_speak called with empty message_content. No message sent.")
        return
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
    original_message: discord.Message,
    action_params: Dict[str, Any],
    deferral_channel_id_str: str
) -> None:
    """
    Handles deferral of a thought/action on Discord.
    It notifies the user who sent the original message and sends a detailed report
    to a specified deferral channel.

    Args:
        discord_client: The active discord.Client instance.
        original_message: The original discord.Message object that led to deferral.
        action_params: Parameters from ActionSelectionPDMAResult, typically containing
                       reasons for deferral and details of the proposed action.
        deferral_channel_id_str: The ID of the Discord channel to send deferral details to.
    """
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
