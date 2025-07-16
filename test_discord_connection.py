#!/usr/bin/env python3
"""Test Discord connection time."""
import discord
import asyncio
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_connection():
    """Test how long it takes to connect to Discord."""
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("ERROR: DISCORD_BOT_TOKEN not found in environment")
        return
    
    print(f"Token found: ...{token[-10:]}")
    
    # Create client with intents
    intents = discord.Intents.default()
    intents.message_content = True
    intents.messages = True
    intents.guilds = True
    intents.members = True
    
    client = discord.Client(intents=intents)
    
    start_time = time.time()
    ready_event = asyncio.Event()
    
    @client.event
    async def on_ready():
        elapsed = time.time() - start_time
        print(f"\n✓ Discord connected in {elapsed:.2f} seconds!")
        print(f"  Logged in as: {client.user}")
        print(f"  Guilds: {len(client.guilds)}")
        for guild in client.guilds:
            print(f"    - {guild.name} (ID: {guild.id})")
        ready_event.set()
    
    # Start connection
    print("\nStarting Discord connection...")
    
    # Create connection task
    connect_task = asyncio.create_task(client.start(token))
    
    # Wait for ready with timeout
    try:
        await asyncio.wait_for(ready_event.wait(), timeout=30.0)
        print("\nConnection successful!")
    except asyncio.TimeoutError:
        print("\nERROR: Connection timed out after 30 seconds")
    finally:
        # Clean up
        await client.close()
        connect_task.cancel()
        try:
            await connect_task
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    asyncio.run(test_connection())