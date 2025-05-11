#!/usr/bin/env python3
import asyncio
import logging
import os
import sys
import argparse # For command-line arguments like log level

# --- Add src directory to sys.path ---
current_script_path = os.path.dirname(os.path.abspath(__file__))
# Assuming this script is in the project root, src_path should be 'src'
src_dir_path = os.path.join(current_script_path, 'src')
if src_dir_path not in sys.path:
    sys.path.insert(0, src_dir_path)
# --- End sys.path modification ---

from openai import AsyncOpenAI
import instructor
from instructor import Mode as InstructorMode

from ciris_engine.utils.logging_config import setup_basic_logging
# from ciris_engine.utils.profile_loader import load_profile # No longer needed here
# from ciris_engine.agent_profile import AgentProfile # No longer needed here
# from agents.discord_agent.ciris_discord_agent import CIRISDiscordAgent # No longer needed here
from ciris_engine.core.config import (
    DEFAULT_OPENAI_MODEL_NAME, # Keep for reference if needed, though bot should use profile's
    DEFAULT_OPENAI_TIMEOUT_SECONDS, # Keep for reference
    DEFAULT_OPENAI_MAX_RETRIES
)

logger = logging.getLogger(__name__)

def main_discord_student(): # Changed to synchronous
    parser = argparse.ArgumentParser(description="Run CIRIS Discord Bot with Student Profile.")
    parser.add_argument("--log-level", type=str, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Set the logging level (default: INFO)")
    args = parser.parse_args()

    # Setup logging
    setup_basic_logging(level=getattr(logging, args.log_level.upper()))

    logger.info("Starting CIRIS Discord Bot with Student Profile...")

    # Profile loading and client configuration are now handled by CIRISDiscordEngineBot
    # --- Get Discord Token ---
    discord_token = os.environ.get("DISCORD_BOT_TOKEN")
    if not discord_token:
        logger.critical("DISCORD_BOT_TOKEN environment variable not set. Cannot start Discord bot.")
        return

    # --- Initialize and Run Discord Agent ---
    try:
        # Instantiate CIRISDiscordEngineBot, passing the desired profile name
        # CIRISDiscordEngineBot will handle profile loading and client setup.
        # NOTE: This assumes CIRISDiscordEngineBot is imported from ciris_discord_bot_alpha.py
        # If you have a separate ciris_discord_bot_student.py that inherits or is similar, adjust the import.
        # For now, assuming we use the modified CIRISDiscordEngineBot from alpha.
        from agents.discord_agent.ciris_discord_bot_alpha import CIRISDiscordEngineBot

        bot_engine = CIRISDiscordEngineBot(profile_name="student")
        # The run method is part of CIRISDiscordEngineBot instance now
        bot_engine.run() # This is a synchronous call that starts the bot's async loop.
        # If CIRISDiscordEngineBot.run() becomes async, then this should be: await bot_engine.run()
        # but typically discord.py's client.run() is blocking.
        # The current CIRISDiscordEngineBot.run() calls self.client.run() which is blocking.
    except Exception as e:
        logger.critical(f"An error occurred while setting up or running the Discord bot: {e}", exc_info=True)

if __name__ == "__main__":
    # asyncio.run is only needed if main_discord_student itself is async
    # and the bot's run method is also async.
    # Given discord.py's client.run() is blocking, main_discord_student doesn't need to be async.
    # Let's simplify assuming main_discord_student will call a blocking run.
    
    # Re-evaluating: The CIRISDiscordEngineBot.run() calls self.client.run(token) which is blocking.
    # However, the setup of the bot (async components like continuous_thought_processing_loop)
    # might benefit from an async main. For now, let's keep main_discord_student async
    # and call the bot's run method. If bot_engine.run() is blocking, asyncio.run() will handle it.

    try:
        main_discord_student() # Call directly
    except KeyboardInterrupt:
        logger.info("Discord bot (Student Profile) shut down by user.")
    except Exception as e:
        logger.critical(f"Unhandled exception in run_discord_student.py: {e}", exc_info=True)
