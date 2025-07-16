#!/usr/bin/env python3
"""Test Discord message sending while CIRIS is running."""
import discord
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def send_test_message():
    """Send a test message to Discord channel."""
    token = os.getenv('DISCORD_BOT_TOKEN')
    channel_id = os.getenv('DISCORD_HOME_CHANNEL_ID')
    
    if not token:
        print("ERROR: DISCORD_BOT_TOKEN not found in environment")
        return
    
    if not channel_id:
        print("ERROR: DISCORD_HOME_CHANNEL_ID not found in environment")
        return
    
    print(f"Token found: ...{token[-10:]}")
    print(f"Channel ID: {channel_id}")
    
    # Create client with intents
    intents = discord.Intents.default()
    intents.message_content = True
    intents.messages = True
    intents.guilds = True
    intents.members = True
    
    client = discord.Client(intents=intents)
    
    @client.event
    async def on_ready():
        print(f"\n✓ Discord connected!")
        print(f"  Logged in as: {client.user}")
        
        # Send test message
        try:
            channel = client.get_channel(int(channel_id))
            if channel:
                await channel.send("$speak Hello from test script! Testing CIRIS Discord connection.")
                print(f"✓ Test message sent to channel {channel.name}")
            else:
                print(f"ERROR: Could not find channel {channel_id}")
        except Exception as e:
            print(f"ERROR sending message: {e}")
        
        # Wait a moment then close
        await asyncio.sleep(2)
        await client.close()
    
    # Start connection
    print("\nConnecting to Discord...")
    
    try:
        await client.start(token)
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(send_test_message())