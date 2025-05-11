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

# Note: OpenAI, instructor imports are handled within CIRISDiscordEngineBot or its dependencies
# from openai import AsyncOpenAI 
# import instructor
# from instructor import Mode as InstructorMode

from ciris_engine.utils.logging_config import setup_basic_logging
# Unused imports related to direct profile/client setup in this script:
# from ciris_engine.utils.profile_loader import load_profile
# from ciris_engine.agent_profile import AgentProfile
# from ciris_engine.core.config import (
#     DEFAULT_OPENAI_MODEL_NAME,
#     DEFAULT_OPENAI_TIMEOUT_SECONDS,
#     DEFAULT_OPENAI_MAX_RETRIES
# )

# Import the main bot class
from agents.discord_agent.ciris_discord_bot_alpha import CIRISDiscordEngineBot


logger = logging.getLogger(__name__)

# The main_discord_teacher function is removed as its logic is directly in the __main__ block.

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run CIRIS Discord Bot with Teacher Profile.")
    parser.add_argument("--log-level", type=str, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Set the logging level (default: INFO)")
    args = parser.parse_args()
    setup_basic_logging(level=getattr(logging, args.log_level.upper()))
    
    logger.info("Preparing to start CIRIS Discord Bot with Teacher Profile...")
    discord_token = os.environ.get("DISCORD_BOT_TOKEN")
    if not discord_token:
        logger.critical("DISCORD_BOT_TOKEN environment variable not set. Cannot start Discord bot.")
        sys.exit(1) # Exit if token is missing

    if not os.environ.get("OPENAI_API_KEY"): # Check for OpenAI key as bot setup will need it
        logger.critical("OPENAI_API_KEY environment variable not set. Bot setup will likely fail.")
        # Depending on strictness, could also sys.exit(1) here.
        # For now, let CIRISDiscordEngineBot handle the critical error if it can't find it.

    try:
        bot_engine = CIRISDiscordEngineBot(profile_name="teacher")
        bot_engine.run() 
    except KeyboardInterrupt:
        logger.info("Discord bot (Teacher Profile) shut down by user.")
    except Exception as e:
        logger.critical(f"Unhandled exception in run_discord_teacher.py: {e}", exc_info=True)
