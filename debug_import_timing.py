#!/usr/bin/env python3
"""Debug script to identify slow imports in Discord adapter."""

import time
import sys

# Track import times
import_times = []

def timed_import(module_name):
    """Import a module and time it."""
    start = time.time()
    module = __import__(module_name, fromlist=[''])
    end = time.time()
    duration = end - start
    import_times.append((module_name, duration))
    print(f"Import {module_name}: {duration:.3f}s")
    return module

# Time key imports
print("Testing import times...\n")

# Core Python
timed_import('asyncio')
timed_import('logging')
timed_import('datetime')

# Third party
print("\nThird party libraries:")
timed_import('discord')

# CIRIS imports
print("\nCIRIS imports:")
timed_import('ciris_engine.schemas.runtime.messages')
timed_import('ciris_engine.protocols.services')
timed_import('ciris_engine.logic.persistence')

# Discord adapter components
print("\nDiscord adapter components:")
timed_import('ciris_engine.logic.adapters.discord.discord_adapter')

# Sort by time
print("\n\nSlowest imports:")
for module, duration in sorted(import_times, key=lambda x: x[1], reverse=True)[:10]:
    if duration > 0.1:
        print(f"  {module}: {duration:.3f}s")

# Now test creating a Discord adapter
print("\n\nTesting Discord adapter creation...")
from ciris_engine.logic.adapters.discord.discord_adapter import DiscordAdapter
from ciris_engine.logic.adapters.discord.config import DiscordAdapterConfig
from ciris_engine.logic.services.lifecycle.time import TimeService
from unittest.mock import Mock, AsyncMock

# Create mocks
def create_mock_discord_client():
    client = Mock()
    client.user = Mock(id=123456789, name="TestBot")
    client.guilds = []
    client.users = []
    client.is_closed = Mock(return_value=False)
    client.is_ready = Mock(return_value=True)
    client.get_channel = Mock(return_value=None)
    client.fetch_channel = AsyncMock()
    return client

def create_mock_bus_manager():
    manager = Mock()
    manager.memory = AsyncMock()
    manager.memory.store = AsyncMock()
    manager.memory.search = AsyncMock(return_value=[])
    manager.memory.memorize_metric = AsyncMock()
    return manager

# Time adapter creation
start = time.time()
time_service = TimeService()
bus_manager = create_mock_bus_manager()
discord_client = create_mock_discord_client()
config = DiscordAdapterConfig(
    deferral_channel_id="987654321",
    monitored_channel_ids=["123456789", "234567890"],
    wa_user_ids=["111111111", "222222222"]
)

adapter = DiscordAdapter(
    token="test_token",
    bot=discord_client,
    time_service=time_service,
    bus_manager=bus_manager,
    config=config
)
end = time.time()

print(f"Discord adapter creation took: {end - start:.3f}s")