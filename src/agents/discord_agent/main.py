"""
CIRIS Discord Agent - Main entry point.

Initializes and runs the CIRIS Discord agent.
"""

import logging
import discord
from ciris_discord_agent import CIRISDiscordAgent
from config import DiscordConfig

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
