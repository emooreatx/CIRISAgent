#!/usr/bin/env python3
"""Test Discord adapter creation timing."""

import time
import asyncio
from unittest.mock import Mock, AsyncMock

# Time imports
print("Testing import timing...")
start = time.time()
from ciris_engine.logic.adapters.discord.discord_adapter import DiscordAdapter
print(f"Import DiscordAdapter: {time.time() - start:.3f}s")

start = time.time()
from ciris_engine.logic.adapters.discord.config import DiscordAdapterConfig
print(f"Import DiscordAdapterConfig: {time.time() - start:.3f}s")

start = time.time()
from ciris_engine.logic.services.lifecycle.time import TimeService
print(f"Import TimeService: {time.time() - start:.3f}s")

start = time.time()
import discord
print(f"Import discord: {time.time() - start:.3f}s")

# Create mocks
def create_mocks():
    """Create all the mocks needed for Discord adapter."""
    mock_time_service = Mock()
    mock_time_service.now = Mock(return_value=None)
    
    mock_bus_manager = Mock()
    mock_bus_manager.memory = AsyncMock()
    mock_bus_manager.memory.store = AsyncMock()
    mock_bus_manager.memory.search = AsyncMock(return_value=[])
    mock_bus_manager.memory.memorize_metric = AsyncMock()
    
    mock_discord_client = Mock(spec=discord.Client)
    mock_discord_client.user = Mock(id=123456789, name="TestBot")
    mock_discord_client.guilds = []
    mock_discord_client.users = []
    mock_discord_client.is_closed = Mock(return_value=False)
    mock_discord_client.is_ready = Mock(return_value=True)
    mock_discord_client.get_channel = Mock(return_value=None)
    mock_discord_client.fetch_channel = AsyncMock()
    
    discord_config = DiscordAdapterConfig(
        deferral_channel_id="987654321",
        monitored_channel_ids=["123456789", "234567890"],
        wa_user_ids=["111111111", "222222222"]
    )
    
    return mock_time_service, mock_bus_manager, mock_discord_client, discord_config

# Test adapter creation
print("\n\nTesting Discord adapter creation...")
start_total = time.time()

# Create mocks
print("Creating mocks...")
start = time.time()
mock_time_service, mock_bus_manager, mock_discord_client, discord_config = create_mocks()
print(f"Mock creation: {time.time() - start:.3f}s")

# Create adapter
print("\nCreating Discord adapter...")
start = time.time()
adapter = DiscordAdapter(
    token="test_token",
    bot=mock_discord_client,
    time_service=mock_time_service,
    bus_manager=mock_bus_manager,
    config=discord_config
)
print(f"Adapter creation: {time.time() - start:.3f}s")

# Test the specific test case
print("\n\nTesting channel_not_found_error scenario...")
async def test_channel_not_found():
    start = time.time()
    
    # Mock channel not found
    adapter._message_handler.send_message_to_channel = AsyncMock(
        side_effect=discord.NotFound(Mock(), "Channel not found")
    )
    
    # Call send_message
    result = await adapter.send_message("999999999", "Test")
    
    print(f"Test execution: {time.time() - start:.3f}s")
    print(f"Result: {result}")
    assert result is False

asyncio.run(test_channel_not_found())

print(f"\n\nTotal time: {time.time() - start_total:.3f}s")