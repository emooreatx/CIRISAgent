import asyncio
import os
from typing import Optional
import click
from ciris_engine.main import main as engine_main
from ciris_engine.runtime.discord_runtime import DiscordRuntime

@click.command()
@click.option("--profile", default="default", help="Agent profile name")
@click.option("--config", type=click.Path(exists=True), help="Path to app config")
@click.option("--debug/--no-debug", default=False, help="Enable debug logging")
def run(profile: str, config: Optional[str], debug: bool) -> None:
    """Run the CIRIS Engine in Discord mode."""
    
    # Get Discord configuration from environment
    discord_token = os.getenv("DISCORD_BOT_TOKEN")
    if not discord_token:
        raise ValueError("DISCORD_BOT_TOKEN environment variable is required")

    # Get channel ID - this is critical for WAKEUP to know where to speak
    discord_channel_id = os.getenv("DISCORD_CHANNEL_ID")
    if not discord_channel_id:
        print("WARNING: DISCORD_CHANNEL_ID not set. WAKEUP will not have a channel to speak in!")
        raise ValueError("DISCORD_CHANNEL_ID environment variable is required for proper operation")

    # Get optional deferral channel ID
    discord_deferral_channel_id = os.getenv("DISCORD_DEFERRAL_CHANNEL_ID")
    if not discord_deferral_channel_id:
        print("INFO: DISCORD_DEFERRAL_CHANNEL_ID not set. Using main channel for deferrals.")
        discord_deferral_channel_id = discord_channel_id

    async def run_discord_runtime():
        # Create runtime with explicit channel configuration
        runtime = DiscordRuntime(
            token=discord_token,
            profile_name=profile,
            startup_channel_id=discord_channel_id,  # This is where WAKEUP will speak
            monitored_channel_id=discord_channel_id,  # This is what it monitors for messages
            deferral_channel_id=discord_deferral_channel_id,  # This is where deferrals go
        )
        
        # Run the agent
        await runtime.run()

    # Run the Discord runtime
    asyncio.run(run_discord_runtime())


if __name__ == "__main__":
    run()
