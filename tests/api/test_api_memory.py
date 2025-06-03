import pytest
import httpx
import os

API_URL = os.environ.get("CIRIS_API_URL", "http://localhost:8080/v1")

def get_scopes_from_response(resp):
    # New API returns {"scopes": [...]}
    data = resp.json()
    if isinstance(data, dict) and "scopes" in data:
        return data["scopes"]
    return data if isinstance(data, list) else []

def get_entries_from_response(resp):
    # New API returns {"entries": [...]}
    data = resp.json()
    if isinstance(data, dict) and "entries" in data:
        return data["entries"]
    return data if isinstance(data, list) else []

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
        scopes = get_scopes_from_response(resp)
        assert isinstance(scopes, list)
        if scopes:
            scope = scopes[0]
            # List entries in the first scope
            entries_resp = await client.get(f"{API_URL}/memory/{scope}/entries")
            assert entries_resp.status_code == 200
            entries_data = get_entries_from_response(entries_resp)
            assert isinstance(entries_data, list)

@pytest.mark.asyncio
async def test_memory_store_and_query():
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    async with httpx.AsyncClient() as client:
        # Store a new entry
        payload = {"key": "pytest-key", "value": "pytest-value"}
        resp = await client.post(f"{API_URL}/memory/local/store", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("result") == "ok"
        # Query the entry
        query = await client.get(f"{API_URL}/memory/local/entries")
        assert query.status_code == 200
        entries = get_entries_from_response(query)
        # Accept both dict and list entries
        found = False
        for e in entries:
            if (isinstance(e, dict) and e.get("key") == "pytest-key") or (isinstance(e, dict) and e.get("id") == "pytest-key"):
                found = True
        assert found
