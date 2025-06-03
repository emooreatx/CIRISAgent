import pytest
import httpx
import os

API_URL = os.environ.get("CIRIS_API_URL", "http://localhost:8080/v1")

async def api_available():
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            resp = await client.get(f"{API_URL}/status")
            return resp.status_code == 200
    except Exception:
        return False

@pytest.mark.asyncio
async def test_memory_scopes_and_entries():
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    async with httpx.AsyncClient() as client:
        # List memory scopes
        resp = await client.get(f"{API_URL}/memory/scopes")
        assert resp.status_code == 200
        scopes = resp.json()
        assert isinstance(scopes, list)
        if scopes:
            scope = scopes[0]
            # List entries in the first scope
            entries = await client.get(f"{API_URL}/memory/{scope}/entries")
            assert entries.status_code == 200
            entries_data = entries.json()
            assert isinstance(entries_data, list)

@pytest.mark.asyncio
async def test_memory_store_and_query():
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    async with httpx.AsyncClient() as client:
        # Store a new entry
        payload = {"key": "pytest-key", "value": "pytest-value"}
        resp = await client.post(f"{API_URL}/memory/default/store", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("result") == "ok"
        # Query the entry
        query = await client.get(f"{API_URL}/memory/default/entries")
        assert query.status_code == 200
        entries = query.json()
        assert any(e.get("key") == "pytest-key" for e in entries)
