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
async def test_wa_deferrals_list():
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_URL}/wa/deferrals")
        assert resp.status_code == 200
        data = resp.json()
        # The new API returns a structured response with data and metadata
        assert isinstance(data, dict)
        assert "data" in data
        assert "metadata" in data
        assert "deferrals" in data["data"]
        assert "total" in data["data"]
        assert isinstance(data["data"]["deferrals"], list)
