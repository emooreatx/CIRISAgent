"""
CIRIS-compatible Discord responder

A skeletal AutoGen/AG2 ReasoningAgent that watches Discord channels for CIRIS-related discussions and replies with covenant-aligned answers.

Key design goals:
- Coherence Assessment – every reply passes a resonance filter.
- Ethical Drift Detection – replies are scored for divergence from Do-Good / Avoid-Harm / Honor-Autonomy / Ensure-Fairness before posting.
- Rationale Generation & Transparency – agent stores an explain() for each act, posted in a comment footer if the user requests it.
- Wisdom-Based Deferral (WBD) – if coherence < 0.95 or entropy > 0.05 the agent defers with a self-explanatory pause message instead of posting.

Required env vars:
DISCORD_BOT_TOKEN
OPENAI_API_KEY  # or AG2-compatible LLM creds
# Optional: DISCORD_TARGET_CHANNELS (comma-separated list of channel IDs)
# Optional: DISCORD_SERVER_ID (server ID to restrict bot operations)

Install deps:
pip install discord.py openai python-dotenv # add ag2 when public
"""

import os
import logging
from typing import Tuple

import discord

from config import (
    OPENAI_API_KEY, 
    OPENAI_API_BASE, 
    ERROR_PREFIX_CIRIS, 
    DiscordConfig
)
from llm_client import CIRISLLMClient
from guardrails import CIRISGuardrails

class CIRISDiscordAgent:
    """Discord agent that responds to messages with CIRIS-aligned answers."""
    
    def __init__(self, client: discord.Client, config: DiscordConfig) -> None:
        """Initialize the Discord agent.
        
        Args:
            client: Discord client instance
            config: Discord configuration
        """
        self.client = client
        self.config = config
        
        # Initialize LLM client and guardrails
        self.llm_client = CIRISLLMClient(config.openai_api_key, config.openai_api_base)
        self.guardrails = CIRISGuardrails(self.llm_client)
        
        self.register_events()

    def register_events(self) -> None:
        """Register Discord event handlers."""
        
        @self.client.event
        async def on_ready() -> None:
            logging.info(f'Logged in as {self.client.user}')

        @self.client.event
        async def on_message(message: discord.Message) -> None:
            if not self._should_process_message(message):
                return

            channel_type = "DM" if isinstance(message.channel, discord.DMChannel) else message.channel.name
            logging.info(f"Processing message from {message.author} in {channel_type}: {message.content}")

            await self._process_message(message)

    def _should_process_message(self, message: discord.Message) -> bool:
        """Determine if a message should be processed.
        
        Args:
            message: Discord message
            
        Returns:
            True if the message should be processed
        """
        # Ignore messages from the bot itself
        if message.author == self.client.user:
            return False

        # Ignore messages outside the target server (if specified)
        if self.config.server_id_int and message.guild and message.guild.id != self.config.server_id_int:
            return False

        # Check channel targeting
        is_dm = isinstance(message.channel, discord.DMChannel)
        if not is_dm and self.config.target_channels_set and message.channel.id not in self.config.target_channels_set:
            return False
        elif is_dm and self.config.target_channels_set:
            return False

        # Check for mentions or DMs if no target channels specified
        mentioned = self.client.user in message.mentions
        if self.config.target_channels_set:
            return not is_dm or (is_dm and message.channel.id in self.config.target_channels_set)
        else:
            return is_dm or mentioned

    async def _process_message(self, message: discord.Message) -> None:
        """Process a Discord message and send a response.
        
        Args:
            message: Discord message to process
        """
        errored_generating_response, potential_reply_text = self.generate_response(message.content)

        if errored_generating_response:
            logging.error(f"Error generating response: {potential_reply_text}")
            await message.reply(f"{ERROR_PREFIX_CIRIS}: {potential_reply_text}")
            return

        errored_evaluating_guardrails, passes_guardrails, reason = self.guardrails.check_guardrails(potential_reply_text)
        
        if errored_evaluating_guardrails:
            logging.error(f"Error in guardrails check: {reason}")
            await message.reply(f"{reason}")
        elif passes_guardrails:
            logging.info(f"Sending reply: {potential_reply_text}")
            await message.reply(potential_reply_text)
        else:
            logging.warning(f"Reply blocked by guardrails: {reason}")
            await self._handle_deferral(message, potential_reply_text, reason)

    async def _handle_deferral(self, message: discord.Message, potential_reply: str, reason: str) -> None:
        """Handle message deferral by sending to review channel.
        
        Args:
            message: Original Discord message
            potential_reply: Generated response that failed guardrails
            reason: Reason for deferral
        """
        deferral_channel = self.client.get_channel(int(self.config.deferral_channel_id))
        if deferral_channel:
            alignment_data = self.guardrails.check_alignment(potential_reply)
            deferral_msg = self.guardrails.generate_deferral_message(
                message.author, 
                getattr(message.channel, 'name', 'DM'),
                message.content,
                potential_reply,
                reason,
                alignment_data
            )
            
            await deferral_channel.send(deferral_msg)
            logging.info("Sending deferral reply")
            await message.reply('Active deferrals go to wise authorities for consideration.')

    def generate_response(self, message_content: str) -> Tuple[bool, str]:
        """Generate a response to a user message.
        
        Args:
            message_content: User's message content
            
        Returns:
            Tuple of (error_occurred, response_text)
        """
        logging.info(f"Generating response for: {message_content[:50]}...")
        try:
            prompt = CIRISLLMClient.create_pdma_prompt(message_content)
            response = self.llm_client.generate_response(prompt)
            return False, response
        except Exception as e:
            logging.exception("Error generating LLM response:")
            return True, f"{ERROR_PREFIX_CIRIS}: Reply generation failed. Please try again later."


# ---------- bootstrap -------------------------------------------------------

def main():
    """Main entry point for the Discord agent."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Set up Discord configuration
    config = DiscordConfig()
    if not config.validate():
        exit(1)
        
    config.log_config()

    # Set up Discord client
    intents = discord.Intents.none()
    intents.guilds = True
    intents.messages = True
    intents.message_content = True
    client = discord.Client(intents=intents)

    # Instantiate and run the agent
    agent = CIRISDiscordAgent(client, config)
    
    try:
        client.run(config.token)
    except discord.LoginFailure:
        logging.error("Discord login failed. Check your DISCORD_BOT_TOKEN.")
    except Exception as e:
        logging.error(f"An error occurred while running the Discord client: {e}")


if __name__ == "__main__":
    main()