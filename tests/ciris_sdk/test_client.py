import pytest
import httpx
from ciris_sdk import CIRISClient

class MockTransport:
    def __init__(self):
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def request(self, method, path, **kwargs):
        self.requests.append((method, path, kwargs))
        return httpx.Response(200, json={"id": "1", "messages": []})

@pytest.mark.asyncio
async def test_send_message(monkeypatch):
    mt = MockTransport()
    client = CIRISClient()
    client._transport = mt
    client.messages._transport = mt
    client.memory._transport = mt
    client.tools._transport = mt
    client.guidance._transport = mt
    async with client:
        await client.messages.send("hi")
    assert mt.requests[0][0] == "POST"

