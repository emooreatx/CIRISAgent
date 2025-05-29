#!/usr/bin/env python3
"""
run_discord.py

Simple script to run CIRIS with Discord integration.
Usage: python run_discord.py [profile_name]
"""
import os
import sys
import asyncio
import logging
from pathlib import Path

# Add parent directory to path if running from scripts directory
sys.path.insert(0, str(Path(__file__).parent))

from ciris_engine.utils.logging_config import setup_basic_logging
from ciris_engine.adapters.discord.discord_runtime import DiscordRuntime

# Configure logging
setup_basic_logging(level=logging.INFO)

# Set up file logging
log_file = Path("discord_agent.log")
file_handler = logging.FileHandler(log_file, mode='a')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
file_handler.setLevel(logging.INFO)

# Add file handler to root logger
root_logger = logging.getLogger()
root_logger.addHandler(file_handler)

# Reduce console logging to WARNING+
for handler in root_logger.handlers:
    if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
        handler.setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def main():
    """Main entry point."""
    # Get configuration from environment
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        logger.error("DISCORD_BOT_TOKEN environment variable not set")
        sys.exit(1)
        
    # Get profile name from command line or environment
    profile_name = "default"
    if len(sys.argv) > 1:
        profile_name = sys.argv[1]
    elif os.getenv("CIRIS_PROFILE"):
        profile_name = os.getenv("CIRIS_PROFILE")
        
    logger.info(f"Starting CIRIS Discord bot with profile: {profile_name}")
    
    # Get optional configuration
    startup_channel = os.getenv("SNORE_CHANNEL_ID") or os.getenv("DISCORD_CHANNEL_ID")
    monitored_channel = os.getenv("DISCORD_CHANNEL_ID")
    deferral_channel = os.getenv("DISCORD_DEFERRAL_CHANNEL_ID")
    max_rounds = int(os.getenv("CIRIS_MAX_ROUNDS", "0")) or None
    
    # Create and run Discord runtime
    runtime = DiscordRuntime(
        token=token,
        profile_name=profile_name,
        startup_channel_id=startup_channel,
        monitored_channel_id=monitored_channel,
        deferral_channel_id=deferral_channel,
    )
    try:
        await runtime.initialize()
    except Exception as e:
        logger.error(f"Failed to initialize Discord runtime: {e}", exc_info=True)
        sys.exit(1)
    logger.info("Discord runtime initialized successfully")
    
    try:
        await runtime.run(max_rounds=max_rounds)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
    finally:
        await runtime.shutdown()
        

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)