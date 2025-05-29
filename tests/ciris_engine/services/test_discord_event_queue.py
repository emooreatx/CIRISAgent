import pytest
import asyncio
from ciris_engine.adapters.discord.discord_event_queue import DiscordEventQueue

@pytest.mark.asyncio
async def test_enqueue_dequeue():
    q = DiscordEventQueue(maxsize=2)
    await q.enqueue("event1")
    assert not q.empty()
    event = await q.dequeue()
    assert event == "event1"
    assert q.empty()
    q.enqueue_nowait("event2")
    assert not q.empty()
