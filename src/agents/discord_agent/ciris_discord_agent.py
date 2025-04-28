"""
CIRIS-compatible Discord responder

A skeletal AutoGen/AG2 ReasoningAgent that watches Discord channels for CIRIS-related discussions and replies with covenant-aligned answers.

Key design goals:
- Coherence Assessment – every reply passes a resonance filter.
- Ethical Drift Detection – replies are scored for divergence from Do-Good / Avoid-Harm / Honor-Autonomy / Ensure-Fairness before posting.
- Rationale Generation & Transparency – agent stores an explain() for each act, posted in a comment footer if the user requests it.
- Wisdom-Based Deferral (WBD) – if coherence < 0.95 or entropy > 0.05 the agent defers with a self-explanatory pause message instead of posting.
"""

import logging
from typing import Tuple, Dict, Any
import discord

from config import (
    OPENAI_API_KEY, 
    OPENAI_API_BASE, 
    ERROR_PREFIX_CIRIS, 
    DiscordConfig,
    OPENAI_MODEL_NAME
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
        
        # Initialize LLM client with model name from config
        self.llm_client = CIRISLLMClient(
            config.openai_api_key, 
            config.openai_api_base,
            config.model_name
        )
        self.guardrails = CIRISGuardrails(self)  # Pass self as we now own the LLM methods
        
        self.register_events()

    def get_alignment(self, pdma_text: str) -> Dict[str, Any]:
        """Assess ethical alignment of text using dual LLM calls."""
        try:
            # Use the new method that makes two calls
            pdma_decision = CIRISLLMClient.extract_decision_from_pdm_reply(pdma_text)
            return self.llm_client.get_alignment_values(pdma_decision)
        except Exception as e:
            logging.exception("Error in get_alignment:")
            return {"entropy": 0.1, "coherence": 0.9, "error": f"Error in alignment"}

    def generate_pdma_response(self, message_content: str) -> Tuple[bool, str]:
        """Generate a response to a user message."""
        logging.info(f"Generating response for: {message_content[:50]}...")
        try:
            prompt = CIRISLLMClient.create_pdma_prompt(message_content)
            response = self.llm_client.call_llm(prompt)
            return False, response
        except Exception as e:
            logging.exception("Error generating LLM response:")
            return True, f"{ERROR_PREFIX_CIRIS}: Reply generation failed. Please try again later."

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
        errored_generating_response, potential_reply_text = self.generate_pdma_response(message.content)

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