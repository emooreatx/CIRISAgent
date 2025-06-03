import pytest
import httpx
import os

API_URL = os.environ.get("CIRIS_API_URL", "http://localhost:8080/v1")

def get_json_field(resp, field, default=None):
    data = resp.json()
    if isinstance(data, dict) and field in data:
        return data[field]
    return default

async def api_available():
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            resp = await client.get(f"{API_URL}/status")
            return resp.status_code == 200
    except Exception:
        return False

@pytest.mark.asyncio
async def test_api_status():
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_URL}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

@pytest.mark.asyncio
async def test_api_messages():
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    async with httpx.AsyncClient() as client:
        # Send a message
        payload = {"content": "Hello from test!"}
        resp = await client.post(f"{API_URL}/messages", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "processed"
        # Get messages
        resp = await client.get(f"{API_URL}/messages?limit=5")
        assert resp.status_code == 200
        messages = get_json_field(resp, "messages", [])
        assert isinstance(messages, list)

@pytest.mark.asyncio
async def test_api_tools():
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_URL}/tools")
        assert resp.status_code == 200
        tools = resp.json()
        assert isinstance(tools, list)
        # Try executing a tool if any exist
        if tools:
            tool_name = tools[0]["name"]
            resp = await client.post(f"{API_URL}/tools/{tool_name}", json={})
            assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_guidance_and_defer():
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    async with httpx.AsyncClient() as client:
        # Guidance
        resp = await client.post(f"{API_URL}/guidance", json={"query": "test guidance"})
        assert resp.status_code == 200
        data = resp.json()
        assert "guidance" in data
        # Defer
        resp = await client.post(f"{API_URL}/defer", json={"thought_id": "test-thought", "reason": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] == "deferred"

@pytest.mark.asyncio
async def test_api_wa_deferrals_and_feedback():
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_URL}/wa/deferrals")
        assert resp.status_code == 200
        # Feedback
        resp = await client.post(f"{API_URL}/wa/feedback", json={"feedback": "test feedback"})
        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data

@pytest.mark.asyncio
async def test_api_audit():
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_URL}/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

@pytest.mark.asyncio
async def test_api_logs():
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    async with httpx.AsyncClient() as client:
        # Try to get the latest log file
        from pathlib import Path
        log_dir = Path("logs")
        log_files = list(log_dir.glob("*.log"))
        if not log_files:
            pytest.skip("No log files found.")
        log_file = log_files[-1].name
        resp = await client.get(f"{API_URL}/logs/{log_file}?tail=10")
        assert resp.status_code == 200
        assert resp.text

@pytest.mark.asyncio
async def test_api_memory():
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    async with httpx.AsyncClient() as client:
        # List memory scopes
        resp = await client.get(f"{API_URL}/memory/scopes")
        assert resp.status_code == 200
        scopes = get_json_field(resp, "scopes", [])
        assert isinstance(scopes, list)
        if scopes:
            scope = scopes[0]
            # Store a new entry
            payload = {"key": "pytest-key", "value": "pytest-value"}
            resp = await client.post(f"{API_URL}/memory/{scope}/store", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("result") == "ok"
            # Query the entry
            query = await client.get(f"{API_URL}/memory/{scope}/entries")
            assert query.status_code == 200
            entries = get_json_field(query, "entries", [])
            found = False
            for e in entries:
                if (isinstance(e, dict) and e.get("key") == "pytest-key") or (isinstance(e, dict) and e.get("id") == "pytest-key"):
                    found = True
            assert found
