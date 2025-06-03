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
    client.audit._transport = mt
    client.logs._transport = mt
    async with client:
        await client.messages.send("hi")
    assert mt.requests[0][0] == "POST"


@pytest.mark.asyncio
async def test_memory_and_tools(monkeypatch):
    mt = MockTransport()
    client = CIRISClient()
    client._transport = mt
    client.memory._transport = mt
    client.tools._transport = mt
    async with client:
        await client.memory.list_scopes()
        await client.tools.list()
    assert mt.requests[0][1] == "/v1/memory/scopes"
    assert mt.requests[1][1] == "/v1/tools"


@pytest.mark.asyncio
async def test_audit_and_logs(monkeypatch):
    mt = MockTransport()
    client = CIRISClient()
    client._transport = mt
    client.audit._transport = mt
    client.logs._transport = mt
    async with client:
        await client.audit.list()
        await client.logs.fetch("latest.log")
    assert mt.requests[0][1] == "/v1/audit"
    assert mt.requests[1][1] == "/v1/logs/latest.log"

