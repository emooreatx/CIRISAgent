import pytest
import asyncio
from ciris_engine.adapters.discord.discord_adapter import DiscordAdapter, DiscordEventQueue

@pytest.mark.asyncio
async def test_discord_event_queue_basic_operations():
    """Test basic queue operations work correctly."""
    q = DiscordEventQueue(maxsize=2)
    
    # Test enqueue/dequeue
    await q.enqueue("event1")
    assert not q.empty()
    event = await q.dequeue()
    assert event == "event1"
    assert q.empty()
    
    # Test nowait operations
    q.enqueue_nowait("event2")
    assert not q.empty()
    event = await q.dequeue()
    assert event == "event2"
    assert q.empty()

@pytest.mark.asyncio
async def test_discord_adapter_initialization():
    """Test that DiscordAdapter can be initialized with a message queue."""
    q = DiscordEventQueue()
    adapter = DiscordAdapter("fake_token", q)
    
    assert adapter.token == "fake_token"
    assert adapter.message_queue is q
    assert adapter.client is None
