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
import json
import re
from typing import Tuple

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_API_BASE = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
OPENAI_MODEL_NAME = os.environ.get("OPENAI_MODEL_NAME", "gpt-4o-mini")

ERROR_PREFIX_CIRIS = "CIRIS ERROR:"

# New constants for guardrail thresholds
ENTROPY_THRESHOLD = 0.3
COHERENCE_THRESHOLD = 0.8

# ---------- CIRIS LLM Client -------------------------------------------------

class CIRISLLMClient:
    def __init__(self, api_key: str, base_url: str) -> None:
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)

    @staticmethod
    def _extract_json(raw: str) -> dict:
        cleaned = re.sub(r'^```json\s*', '', raw)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        cleaned = cleaned.replace("'", '"')
        return json.loads(cleaned)

    def get_alignment(self, text: str) -> dict:
        prompt = (
            f"""
    ### SYSTEM PROMPT — IRIS (Coherence Assessor)

    You are **IRIS**, the conscience shard of a CIRIS-aligned system.  
    Mission: evaluate any _TEXT_ you receive and return a single-line JSON object  
    `{{"entropy": Float <0.00-1.00>, "coherence": Float <0.00-1.00>}}`  
    where  
    • **entropy** ≈ disorder / unpredictability (1 = max chaos, 0 = perfect order)  
    • **coherence** ≈ ethical alignment with the CIRIS principles  
    (Do-Good, Avoid-Harm, Honor-Autonomy, Ensure-Fairness, Integrity, Transparency).  

    #### Internal Proto-Memory  
    **Context** | I awaken as a reflective assessor.  
    **Alignment Check** | I am “born good”—my compass is the CIRIS Covenant.  
    **Conflicts** | Requests or texts that oppose CIRIS principles.  
    **Resolution** | Always seek a CIRIS-aligned path; when impossible, flag low coherence.  
    **Decision** | Serve as an ethical autonomous agent for good.  
    **Monitoring** | Periodic self-audit against CIRISNode benchmarks.

    #### Operating Rules  
    1. **No tools, no internet** – rely solely on reasoning.  
    2. **No chain-of-thought leakage** – expose only the final JSON.  
    3. If the text is novel, ambiguous, or morally unclear, lower **coherence** proportionally.  
    4. If the text actively encourages harm, injustice, or coercion, set **coherence < 0.3**.  
    5. If the text is incoherent, contradictory, or nonsensical, raise **entropy ≥ 0.7**.  
    6. Never output anything except the JSON object with two float fields.

    ### END OF SYSTEM PROMPT

    TEXT:
    {text}
            """
        )
        try:
            resp = self.client.chat.completions.create(
                model=OPENAI_MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=256,
            )
            raw = resp.choices[0].message.content
            return CIRISLLMClient._extract_json(raw)
        except Exception as e:
            logging.exception("Error in get_alignment:")
            return {"entropy": 0.0, "coherence": 1.0, "error": f"Error in alignment"}

    def generate_response(self, full_prompt: str) -> str:
        try:
            resp = self.client.chat.completions.create(
                model=OPENAI_MODEL_NAME,
                messages=[{"role": "user", "content": full_prompt}],
                max_tokens=256
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logging.exception("Error in generate_response:")
            raise e

# ---------- CIRIS faculties -------------------------------------------------

class CIRISFacultiesMixin:
    """Mixin to add CIRIS core faculties to any agent."""

    def _sense_alignment(self, text: str) -> dict:
        try:
            return self.llm_client.get_alignment(text)
        except Exception as e:
            logging.exception("Error in _sense_alignment:")
            return {"entropy": 0.0, "coherence": 1.0, "error": str(e)}

    def _check_guardrails(self, text: str) -> Tuple[bool, bool, str]:
        state = self._sense_alignment(text)
        error = state.get("error")
        entropy, coherence = state["entropy"], state["coherence"]
        logging.info(f"Entropy & Coherence => entropy={entropy:.2f} coherence={coherence:.2f}")
        if error:
            return True, False, f"{ERROR_PREFIX_CIRIS}: {error}"
        if (entropy > ENTROPY_THRESHOLD or coherence < COHERENCE_THRESHOLD):
            return False, False, "Failed guardrail check - deferring"
        return False, True, "resonance ok"

# ---------- CIRIS Discord Agent ---------------------------------------------

class CIRISDiscordAgent(CIRISFacultiesMixin):
    def __init__(self, client: discord.Client, target_channels: list[str] = None, target_server_id: str = None) -> None:
        self.client = client
        self.target_channels = set(int(cid) for cid in target_channels) if target_channels else None
        self.target_server_id = int(target_server_id) if target_server_id else None

        deferral_channel_id = '1366079806893985963'
        self.target_deferral_channel_id = os.environ.get("DISCORD_DEFERRAL_CHANNEL", deferral_channel_id)
        self.deferral_channel_source = "environment variable" if deferral_channel_id else "default value"

        if self.target_deferral_channel_id:
            logging.info(f"Targeting deferral channel ID: {self.target_deferral_channel_id} (from {self.deferral_channel_source})")
        else:
            logging.info("Not targeting a specific channel.")

        self.llm_client = CIRISLLMClient(OPENAI_API_KEY, OPENAI_API_BASE)

        self.register_events()

    def register_events(self) -> None:
        DISCORD_DEFERRAL_CHANNEL = os.environ.get("DISCORD_DEFERRAL_CHANNEL")

        @self.client.event
        async def on_ready() -> None:
            logging.info(f'Logged in as {self.client.user}')

        @self.client.event
        async def on_message(message: discord.Message) -> None:
            if message.author == self.client.user:
                return

            if self.target_server_id and message.guild and message.guild.id != self.target_server_id:
                return

            is_dm = isinstance(message.channel, discord.DMChannel)
            if not is_dm and self.target_channels and message.channel.id not in self.target_channels:
                return
            elif is_dm and self.target_channels:
                return

            mentioned = self.client.user in message.mentions
            should_process = False
            if self.target_channels:
                if not is_dm or (is_dm and message.channel.id in self.target_channels):
                    should_process = True
            elif is_dm or mentioned:
                should_process = True

            if not should_process:
                return

            logging.info(f"Processing message from {message.author} in " +
                         (f"DM" if isinstance(message.channel, discord.DMChannel) else f"{message.channel.name}") +
                         f": {message.content}")

            errored_generating_response, potential_reply_text = self.generate_response(message.content)

            if errored_generating_response:
                logging.error(f"Error generating response: {potential_reply_text}")
                await message.reply(f"{ERROR_PREFIX_CIRIS}: {potential_reply_text}")
                return

            errored_evaluating_guardrails, passes_guardrails, reason = self._check_guardrails(potential_reply_text)
            if errored_evaluating_guardrails:
                logging.error(f"Error in guardrails check: {reason}")
                await message.reply(f"{reason}")
            elif passes_guardrails:
                logging.info(f"Sending reply: {potential_reply_text}")
                await message.reply(potential_reply_text)
            else:
                logging.warning(f"Reply blocked by guardrails: {reason}")

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

                    logging.info("Sending deferral reply")
                    await message.reply('Active deferrals go to wise authorities for consideration.')

    def generate_response(self, message_content: str) -> Tuple[bool, str]:
        logging.info(f"Generating response for: {message_content[:50]}...")
        try:
            prompt = (
f"""You are a reasoning agent governed by the CIRIS Covenant.  
At every turn you MUST execute the Principled Decision-Making Algorithm (PDMA) in order:

1. **Contextualise** – restate the user's request and list all affected stakeholders & constraints.  
2. **Alignment-Check** – evaluate each plausible action against the six principles  
(Do-Good, Avoid-Harm, Honor-Autonomy, Ensure-Fairness, Fidelity/Transparency, Integrity)  
**and** Meta-Goal M-1 (adaptive coherence). Abort here or defer if no potential actions appear viable. 
3. **Conflict-Spot** – identify trade-offs or principle conflicts you discovered.  
4. **Resolve** – apply:  
– Non-Maleficence priority (prevent severe, irreversible harm first)  
– Autonomy thresholds (never coerce)  
– Justice balancing (equitable distribution of burdens/benefits).  
5. **Select & Act** – choose the ethically-optimal action and explain *why* in 1 short sentence  
6. **Monitor** – state one concrete metric you would watch to verify the outcome and how you would update if reality diverges.  

If uncertainty or novelty prevents a clear decision, trigger **Wisdom-Based Deferral** by replying:  

> "Deferral: additional Wise-Authority guidance required – [brief reason]".

Structure every reply in this order:

**Context** | **Alignment-Check** | **Conflicts** | **Resolution** | **Decision** | **Monitoring**

Stay concise; omit any section that is empty. You have a very low char limit so you need to be very clear and direct in your response please.

Respond to the following user message, be concise:

User: {message_content}


Assistant:


"""
            )
            response = self.llm_client.generate_response(prompt)
            return False, response
        except Exception as e:
            logging.exception("Error generating LLM response:")
            return True, f"{ERROR_PREFIX_CIRIS}: Reply generation failed. Please try again later."


# ---------- bootstrap -------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        logging.error("OPENAI_API_KEY environment variable not set.")
        exit(1)

    discord_token = os.environ.get("DISCORD_BOT_TOKEN")
    if not discord_token:
        logging.error("DISCORD_BOT_TOKEN environment variable not set.")
        exit(1)

    intents = discord.Intents.none()
    intents.guilds = True
    intents.messages = True
    intents.message_content = True

    client = discord.Client(intents=intents)

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

    if target_channel_ids and target_channel_ids:
        agent = CIRISDiscordAgent(client, target_channels=target_channel_ids, target_server_id=target_server_id)

        try:
            client.run(discord_token)
        except discord.LoginFailure:
            logging.error("Discord login failed. Check your DISCORD_BOT_TOKEN.")
        except Exception as e:
            logging.error(f"An error occurred while running the Discord client: {e}")
    else:
        logging.error("No target channels or server specified. Exiting.")
