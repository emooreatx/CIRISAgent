import pytest
from unittest.mock import AsyncMock

from ciris_engine.services.discord_observer import DiscordObserver
from ciris_engine.services.discord_event_queue import DiscordEventQueue
from ciris_engine.runtime.base_runtime import IncomingMessage
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

    q = DiscordEventQueue()
    observer = DiscordObserver(collect, message_queue=q, monitored_channel_id="allowed")
    msg1 = IncomingMessage(message_id="1", author_id="1", author_name="nick", content="hello", channel_id="ignored")
    await observer.handle_incoming_message(msg1)
    assert events == []

    msg2 = IncomingMessage(message_id="2", author_id="1", author_name="nick", content="hi there", channel_id="allowed")
    await observer.handle_incoming_message(msg2)
    assert events == [
        {
            "type": "OBSERVATION",
            "message_id": "2",
            "content": "hi there",
            "context": {
                "origin_service": "discord",
                "author_id": "1",
                "author_name": "nick",
                "channel_id": "allowed",
            },
            "task_description": (
                "Observed user @nick (ID: 1) in channel #allowed (Msg ID: 2) say: 'hi there'. Evaluate and decide on the appropriate course of action."
            ),
        }
    ]


@pytest.mark.asyncio
async def test_discord_observer_queue_polling():
    events = []

    async def collect(payload):
        events.append(payload)

    q = DiscordEventQueue()
    observer = DiscordObserver(collect, message_queue=q, monitored_channel_id="allowed")
    await observer.start()
    await q.enqueue(IncomingMessage(message_id="3", author_id="1", author_name="nick", content="hi", channel_id="allowed"))
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
