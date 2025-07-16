#!/usr/bin/env python3
"""Test Discord bot token from .env file"""

import os
import asyncio
import discord
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env')

# Get Discord token
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
CHANNEL_IDS = os.getenv('DISCORD_CHANNEL_IDS', '').split(',')
HOME_CHANNEL = os.getenv('DISCORD_HOME_CHANNEL_ID')

print(f"Discord Bot Token: {TOKEN[:20]}...{TOKEN[-10:] if TOKEN else 'NOT FOUND'}")
print(f"Home Channel ID: {HOME_CHANNEL}")
print(f"Channel IDs: {CHANNEL_IDS}")

if not TOKEN:
    print("ERROR: No Discord bot token found in .env")
    exit(1)

# Create a simple Discord client with minimal intents
intents = discord.Intents.default()
intents.guilds = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'\n✅ Successfully logged in as {client.user}')
    print(f'Bot ID: {client.user.id}')
    print(f'Connected to {len(client.guilds)} guild(s)')
    
    # List guilds and channels
    for guild in client.guilds:
        print(f'\nGuild: {guild.name} (ID: {guild.id})')
        
        # Check if we can access the configured channels
        for channel_id in CHANNEL_IDS:
            if channel_id:
                channel = guild.get_channel(int(channel_id))
                if channel:
                    print(f'  ✅ Can access channel: #{channel.name} ({channel.id})')
                else:
                    print(f'  ❌ Cannot access channel: {channel_id}')
    
    # Disconnect after testing
    await client.close()

@client.event
async def on_error(event, *args, **kwargs):
    print(f"❌ Error in {event}: {args}")

async def main():
    try:
        print("\nAttempting to connect to Discord...")
        await client.start(TOKEN)
    except discord.LoginFailure:
        print("❌ Failed to login - Invalid token")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(main())