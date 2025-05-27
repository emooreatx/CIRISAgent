import asyncio
import pytest
from ciris_engine.ports import EventSource, ActionSink

class FakeEventSource(EventSource):
    def __init__(self, events):
        self.events = events
        self.started = False
    async def start(self):
        self.started = True
    async def stop(self):
        self.started = False
    def __aiter__(self):
        async def gen():
            for e in self.events:
                yield e
        return gen()

class FakeActionSink(ActionSink):
    def __init__(self):
        self.messages = []
        self.started = False
    async def start(self):
        self.started = True
    async def stop(self):
        self.started = False
    async def send_message(self, channel_id: str, content: str):
        self.messages.append((channel_id, content))
    async def run_tool(self, tool_name: str, arguments: dict):
        self.messages.append((tool_name, arguments))

@pytest.mark.asyncio
async def test_fake_ports_iteration():
    source = FakeEventSource([{"channel": "1", "content": "hi"}])
    sink = FakeActionSink()
    await source.start()
    events = [e async for e in source]
    await source.stop()
    assert events == [{"channel": "1", "content": "hi"}]
    await sink.start()
    await sink.send_message("1", "ok")
    await sink.stop()
    assert sink.messages == [("1", "ok")]
