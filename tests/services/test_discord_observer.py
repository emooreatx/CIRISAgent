import pytest
from unittest.mock import AsyncMock

from ciris_engine.services.discord_observer import DiscordObserver

@pytest.mark.asyncio
async def test_discord_observer_filters_channels():
    events = []

    async def collect(payload):
        events.append(payload)

    observer = DiscordObserver(collect, allowed_channel_ids={"allowed"})
    await observer.handle_event("nick", "ignored")
    assert events == []

    await observer.handle_event("nick", "allowed")
    assert events == [{"user_nick": "nick", "channel": "allowed"}]
