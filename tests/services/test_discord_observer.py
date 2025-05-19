import pytest
from unittest.mock import AsyncMock

from ciris_engine.services.discord_observer import DiscordObserver
from ciris_engine.services.discord_event_queue import DiscordEventQueue
from ciris_engine.services.discord_service import DiscordService
from ciris_engine.core.action_dispatcher import ActionDispatcher
from datetime import datetime, timezone
import logging
import asyncio

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


@pytest.mark.asyncio
async def test_discord_observer_queue_polling():
    events = []

    async def collect(payload):
        events.append(payload)

    q = DiscordEventQueue()
    observer = DiscordObserver(collect, monitored_channel_id="allowed", event_queue=q)
    await observer.start()
    await q.enqueue({"user_nick": "nick", "channel": "allowed", "message_content": "hi"})
    await asyncio.sleep(0.05)
    await observer.stop()
    assert len(events) == 1


@pytest.mark.asyncio
async def test_discord_service_non_blocking_enqueue(monkeypatch, caplog):
    caplog.set_level(logging.WARNING)
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "x")
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "2")

    q = DiscordEventQueue(maxsize=1)
    q.enqueue_nowait({"user_nick": "a", "channel": "1", "message_content": "hi"})

    dispatcher = ActionDispatcher()
    service = DiscordService(dispatcher, event_queue=q)

    class Author:
        def __init__(self):
            self.name = "u"
            self.id = 1
            self.bot = False

    class Channel:
        def __init__(self):
            self.id = 2
            self.name = "c"

    class Message:
        def __init__(self):
            self.id = 3
            self.author = Author()
            self.channel = Channel()
            self.content = "hello"
            self.created_at = datetime.now(timezone.utc)
            self.guild = None
            self.reference = None

    msg = Message()
    await service.bot.on_message(msg)

    assert any("Event queue full" in rec.message for rec in caplog.records)
