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

# Tools endpoint removed - tools are now managed internally by the agent
# Guidance and defer endpoints removed - these are internal agent operations

@pytest.mark.asyncio
async def test_api_wa_deferrals():
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_URL}/wa/deferrals")
        assert resp.status_code == 200
        data = resp.json()
        # The new API returns a structured response
        assert isinstance(data, dict)
        assert "data" in data
        assert "metadata" in data

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
