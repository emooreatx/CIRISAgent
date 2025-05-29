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
from ciris_engine.utils.logging_config import setup_basic_logging
from ciris_engine.adapters.discord.discord_runtime import DiscordRuntime
import discord

# Add parent directory to path if running from scripts directory
sys.path.insert(0, str(Path(__file__).parent))

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


async def run_discord_bot():
    """Main entry point."""
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        logger.error("DISCORD_BOT_TOKEN environment variable not set")
        sys.exit(1)

    profile_name = "default"
    if len(sys.argv) > 1:
        profile_name = sys.argv[1]
    elif os.getenv("CIRIS_PROFILE"):
        profile_name = os.getenv("CIRIS_PROFILE")

    logger.info(f"Starting CIRIS Discord bot with profile: {profile_name}")
    startup_channel = os.getenv("SNORE_CHANNEL_ID") or os.getenv("DISCORD_CHANNEL_ID")
    monitored_channel = os.getenv("DISCORD_CHANNEL_ID")
    deferral_channel = os.getenv("DISCORD_DEFERRAL_CHANNEL_ID")
    max_rounds = int(os.getenv("CIRIS_MAX_ROUNDS", "0")) or None

    runtime = DiscordRuntime(
        token=token,
        profile_name=profile_name,
        startup_channel_id=startup_channel,
        monitored_channel_id=monitored_channel,
        deferral_channel_id=deferral_channel,
    )
    await runtime.initialize()
    client = runtime.client
    # Attach DiscordAdapter event handlers to the client
    runtime.discord_adapter.attach_to_client(client)

    @client.event
    async def on_ready():
        logger.info(f"Discord bot logged in as {client.user}")
        # Start CIRIS agent logic only after bot is ready
        asyncio.create_task(runtime.discord_observer.start())
        await runtime.action_sink.start()
        await runtime.deferral_sink.start()
        # If you have feedback sinks/queues, start them here as well
        if hasattr(runtime, 'feedback_sink') and runtime.feedback_sink:
            await runtime.feedback_sink.start()
        # If you have tool registry or tool sinks, ensure they're initialized here if needed
        logger.info("CIRIS agent services started after Discord client ready.")
        # Start the CIRIS agent processor (wakeup logic)
        if hasattr(runtime, "agent_processor") and runtime.agent_processor:
            await runtime.agent_processor.start_processing()
        else:
            logger.warning("No agent_processor found to start wakeup logic.")

    try:
        await client.start(token)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
    finally:
        await runtime.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(run_discord_bot())
    except KeyboardInterrupt:
        print("\nShutdown complete")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)