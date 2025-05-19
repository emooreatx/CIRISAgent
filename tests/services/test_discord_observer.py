import pytest
from unittest.mock import AsyncMock

from ciris_engine.services.discord_observer import DiscordObserver

@pytest.mark.asyncio
async def test_discord_observer_filters_channels():
    events = []

    async def collect(payload):
        events.append(payload)

    observer = DiscordObserver(collect, monitored_channel_id="allowed")
    await observer.handle_event("nick", "ignored", "hello")
    assert events == []

    await observer.handle_event("nick", "allowed", "hi there")
    assert events == [
        {
            "type": "OBSERVATION",
            "context": {
                "user_nick": "nick",
                "channel": "allowed",
                "message_text": "hi there",
            },
            "task_description": (
                "As a result of your permanent job task, you observed user @nick in channel #allowed say: 'hi there'. Use your decision-making algorithms to decide whether to respond, ignore, or take any other appropriate action."
            ),
        }
    ]
