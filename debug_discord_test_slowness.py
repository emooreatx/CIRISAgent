#!/usr/bin/env python3
"""Debug script to identify what's causing the Discord adapter test slowness."""

import time
import asyncio
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timezone

# Import the components
from ciris_engine.logic.adapters.discord.discord_adapter import DiscordAdapter
from ciris_engine.logic.adapters.discord.config import DiscordAdapterConfig
from ciris_engine.logic.services.lifecycle.time import TimeService

def create_mock_discord_client():
    """Create a mock Discord client."""
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
    """Create a mock bus manager."""
    manager = Mock()
    manager.memory = AsyncMock()
    manager.memory.store = AsyncMock()
    manager.memory.search = AsyncMock(return_value=[])
    manager.memory.memorize_metric = AsyncMock()
    return manager

def measure_time(func, *args, **kwargs):
    """Measure execution time of a function."""
    start = time.time()
    result = func(*args, **kwargs)
    end = time.time()
    return result, end - start

async def test_adapter_initialization():
    """Test Discord adapter initialization with timing."""
    print("Testing Discord adapter initialization...")
    
    # Create components with timing
    print("\n1. Creating TimeService...")
    time_service, time_duration = measure_time(TimeService)
    print(f"   TimeService creation took: {time_duration:.3f}s")
    
    print("\n2. Creating mock bus manager...")
    bus_manager, bus_duration = measure_time(create_mock_bus_manager)
    print(f"   Bus manager creation took: {bus_duration:.3f}s")
    
    print("\n3. Creating mock Discord client...")
    discord_client, client_duration = measure_time(create_mock_discord_client)
    print(f"   Discord client creation took: {client_duration:.3f}s")
    
    print("\n4. Creating Discord config...")
    config, config_duration = measure_time(
        DiscordAdapterConfig,
        deferral_channel_id="987654321",
        monitored_channel_ids=["123456789", "234567890"],
        wa_user_ids=["111111111", "222222222"]
    )
    print(f"   Config creation took: {config_duration:.3f}s")
    
    print("\n5. Creating Discord adapter...")
    start_total = time.time()
    
    # Temporarily patch imports to measure their time
    import ciris_engine.logic.adapters.discord.discord_adapter as discord_module
    
    # Measure handler imports
    handlers = [
        'discord_message_handler',
        'discord_guidance_handler', 
        'discord_channel_manager',
        'discord_reaction_handler',
        'discord_audit',
        'discord_connection_manager',
        'discord_error_handler',
        'discord_rate_limiter',
        'discord_embed_formatter',
        'discord_access_control',
        'discord_tool_handler'
    ]
    
    print("\n   Importing handler modules:")
    for handler in handlers:
        try:
            start = time.time()
            module = __import__(f'ciris_engine.logic.adapters.discord.{handler}', fromlist=[handler])
            end = time.time()
            print(f"     {handler}: {end - start:.3f}s")
        except Exception as e:
            print(f"     {handler}: Failed - {e}")
    
    # Now create the adapter
    print("\n   Creating adapter instance...")
    adapter_start = time.time()
    adapter = DiscordAdapter(
        token="test_token",
        bot=discord_client,
        time_service=time_service,
        bus_manager=bus_manager,
        config=config
    )
    adapter_end = time.time()
    
    total_time = adapter_end - start_total
    print(f"\n   Adapter instantiation took: {adapter_end - adapter_start:.3f}s")
    print(f"   Total adapter creation (with imports): {total_time:.3f}s")
    
    # Test a simple method
    print("\n6. Testing send_message method...")
    method_start = time.time()
    adapter._message_handler.send_message_to_channel = AsyncMock(
        side_effect=Exception("Channel not found")
    )
    result = await adapter.send_message("999999999", "Test")
    method_end = time.time()
    print(f"   send_message took: {method_end - method_start:.3f}s")
    print(f"   Result: {result}")
    
    print("\n\nTotal test time breakdown:")
    print(f"  TimeService:    {time_duration:.3f}s")
    print(f"  Bus manager:    {bus_duration:.3f}s")
    print(f"  Discord client: {client_duration:.3f}s")
    print(f"  Config:         {config_duration:.3f}s")
    print(f"  Adapter:        {total_time:.3f}s")
    print(f"  Method call:    {method_end - method_start:.3f}s")
    print(f"  TOTAL:          {time.time() - start_total:.3f}s")

if __name__ == "__main__":
    asyncio.run(test_adapter_initialization())