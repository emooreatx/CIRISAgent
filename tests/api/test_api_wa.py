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
async def test_wa_deferrals_list_and_detail():
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_URL}/wa/deferrals")
        assert resp.status_code == 200
        deferrals = resp.json()
        assert isinstance(deferrals, list)
        if deferrals:
            deferral_id = deferrals[0].get("id")
            detail = await client.get(f"{API_URL}/wa/deferrals/{deferral_id}")
            assert detail.status_code == 200
            detail_data = detail.json()
            assert detail_data.get("id") == deferral_id

@pytest.mark.asyncio
async def test_wa_feedback():
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    async with httpx.AsyncClient() as client:
        payload = {"thought_id": "pytest-wa-feedback", "feedback": "pytest WA feedback"}
        resp = await client.post(f"{API_URL}/wa/feedback", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
