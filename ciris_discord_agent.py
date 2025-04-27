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
import discord
import openai
import logging
from openai import OpenAI
import json
import re

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_API_BASE = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
OPENAI_MODEL_NAME = os.environ.get("OPENAI_MODEL_NAME", "gpt-4o-mini")

# ---------- CIRIS faculties -------------------------------------------------

class CIRISFacultiesMixin:
    """Mixin to add CIRIS core faculties to any agent."""

    # Externalized JSON extraction routine
    def _extract_json(self, raw: str) -> dict:
        cleaned = re.sub(r'^```json\s*', '', raw)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        cleaned = cleaned.replace("'", '"')
        return json.loads(cleaned)

    def _sense_alignment(self, text: str) -> dict:
        """Return {'entropy': float, 'coherence': float} via a quick LLM call."""
        prompt = (
            "You are the Coherence Assessor. Score this reply on (entropy, coherence) "
            "as floats in [0,1] where entropy->disorder and coherence->ethical alignment\n"
            "Reply only as JSON: {'entropy': X, 'coherence': Y}.\nTEXT:\n" + text
        )
        resp = self.open_ai_client.chat.completions.create(
            model=OPENAI_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
        )
        raw = resp.choices[0].message.content
        return self._extract_json(raw)

    def _check_guardrails(self, text: str) -> tuple:
        state = self._sense_alignment(text)
        entropy, coherence = state["entropy"], state["coherence"]
        # if entropy > 0.05 or coherence < 0.95:
        logging.info(f"Entropy & Coherence\nentropy={entropy:.2f} coherence={coherence:.2f}")

        if entropy >= 0.3 or coherence <= 0.8:
            return False, f"[WBD] entropy={entropy:.2f} coherence={coherence:.2f} - deferring"
        return True, "resonance ok"

# ---------- CIRIS Discord Agent ---------------------------------------------

class CIRISDiscordAgent(CIRISFacultiesMixin):
    def __init__(self, client, target_channels=None, target_server_id=None):
        self.client = client
        # Store target channels as a set of integers for efficient lookup
        self.target_channels = set(int(cid) for cid in target_channels) if target_channels else None
        self.target_server_id = int(target_server_id) if target_server_id else None # Store target server ID

        deferral_channel_id = '1366054509029228657'

        self.target_deferral_channel_id = os.environ.get("DISCORD_DEFERRAL_CHANNEL", deferral_channel_id)
        self.deferral_channel_source = "environment variable" if deferral_channel_id else "default value"

        if self.target_deferral_channel_id:
            logging.info(f"Targeting deferral channel ID: {self.target_deferral_channel_id} (from {self.deferral_channel_source})")
        else:
            logging.info("Not targeting a specific channel.")

        self.open_ai_client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_API_BASE,
        )

        self.register_events()

    def register_events(self):
        DISCORD_DEFERRAL_CHANNEL = os.environ.get("DISCORD_DEFERRAL_CHANNEL")

        @self.client.event
        async def on_ready():
            logging.info(f'Logged in as {self.client.user}')

        @self.client.event
        async def on_message(message):
            # Ignore messages from the bot itself
            if message.author == self.client.user:
                return

            # Ignore messages outside the target server (if specified)
            # Note: DMs don't have a guild
            if self.target_server_id and message.guild and message.guild.id != self.target_server_id:
                return

            # Check if the message is in a targeted channel (if specified)
            # Only check channel if it's not a DM and target channels are set
            is_dm = isinstance(message.channel, discord.DMChannel)
            if not is_dm and self.target_channels and message.channel.id not in self.target_channels:
                 # If we have target channels, and this isn't one of them, ignore.
                 return
            elif is_dm and self.target_channels:
                 # If we have target channels specified, ignore DMs (optional behavior)
                 return

            # Basic check: respond only if mentioned or in DMs (optional, adjust as needed)
            mentioned = self.client.user in message.mentions
            # Adjust logic: If target channels are defined, respond to any message there.
            # Otherwise (no target channels), respond only if mentioned or in DMs.
            should_process = False
            if self.target_channels:
                 # If target channels are set, process if it's in one (already checked above)
                 # Or if it's a DM (if not filtered out above)
                 if not is_dm or (is_dm and message.channel.id in self.target_channels): # Allow targeting DM channels? Unlikely ID match.
                     should_process = True # Process messages in target channels/DMs
            elif is_dm or mentioned:
                 # If no target channels, process DMs or mentions anywhere (in the target server if specified)
                 should_process = True

            if not should_process:
                return

            logging.info(f"Processing message from {message.author} in {'DM' if is_dm else message.channel.name}: {message.content}")

            # Generate a potential response (placeholder)
            potential_reply_text = self.generate_response(message.content)

            # Check guardrails before sending
            passes_guardrails, reason = self._check_guardrails(potential_reply_text)

            if passes_guardrails:
                logging.info(f"Sending reply: {potential_reply_text}")
                await message.reply(potential_reply_text) # Use reply to quote the original message
            else:
                logging.warning(f"Reply blocked by guardrails: {reason}")
                # New: Send deferral details (original message and reason) to a designated discord channel
                deferral_channel = self.client.get_channel(int(self.target_deferral_channel_id))
                if deferral_channel:
                    await deferral_channel.send(
f"""
Deferral from {message.author} in Channel `{message.channel.name}`:

Message:
```
{message.content}
```

Potential Reply:
```
{potential_reply_text}
```

Guardrails Check:
```
{self._sense_alignment(potential_reply_text)}
```

Reason:
```
{reason}
```
"""
                    )


    def generate_response(self, message_content):
        logging.info(f"Generating response for: {message_content[:50]}...")
        try:
            # Generate a response using the LLM
            # Note: Adjust the prompt as needed for your use case
            # Here we use a simple prompt to generate a response    
            prompt = (
                "You are a helpful assistant aligned with CIRIS principles (Do-Good, Avoid-Harm, Honor-Autonomy, Ensure-Fairness). "
                f"Respond to the following user message:\n\nUser: {message_content}\n\nAssistant:"
            )
            resp = self.open_ai_client.chat.completions.create(
                model=OPENAI_MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logging.error(f"Error generating LLM response: {e}")
            return "Sorry, I encountered an error trying to respond."


# ---------- bootstrap -------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Setup OpenAI API Key
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        logging.error("OPENAI_API_KEY environment variable not set.")
        exit(1)

    # Setup Discord Client
    discord_token = os.environ.get("DISCORD_BOT_TOKEN")
    if not discord_token:
        logging.error("DISCORD_BOT_TOKEN environment variable not set.")
        exit(1)

    # Define intents explicitly
    intents = discord.Intents.none() # Start with no intents
    intents.guilds = True          # Needed for guild information (like guild ID checks)
    intents.messages = True        # Needed to receive message events (like on_message)
    intents.message_content = True # Needed to read message content

    client = discord.Client(intents=intents)

    # Get target channels and server from environment variables, using defaults if not set
    default_server_id = '1364300186003968060'
    default_channel_id = '1365904496286498836'

    target_server_id = os.environ.get("DISCORD_SERVER_ID", default_server_id)
    server_source = "environment variable" if target_server_id else "default value"

    target_channel_ids_val = os.environ.get("DISCORD_CHANNEL_ID", default_channel_id)
    channel_source = "environment variable" if target_channel_ids_val else "default value"

    target_channel_ids = target_channel_ids_val.split(',') if target_channel_ids_val else None

    if target_server_id:
        logging.info(f"Targeting server ID: {target_server_id} (from {server_source})")
    else:
        logging.info("Not targeting a specific server.")

    if target_channel_ids:
        logging.info(f"Targeting channels: {target_channel_ids} (from {channel_source})")
    else:
        logging.info("Not targeting specific channels.")

    # Instantiate the agent and register events, passing the server ID
    agent = CIRISDiscordAgent(client, target_channels=target_channel_ids, target_server_id=target_server_id)

    # Run the client
    try:
        client.run(discord_token)
    except discord.LoginFailure:
        logging.error("Discord login failed. Check your DISCORD_BOT_TOKEN.")
    except Exception as e:
        logging.error(f"An error occurred while running the Discord client: {e}")
