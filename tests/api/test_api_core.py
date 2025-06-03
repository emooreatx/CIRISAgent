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
async def test_comms_send_and_receive():
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    async with httpx.AsyncClient() as client:
        payload = {
            "content": "Test comms message",
            "channel_id": "pytest_comms",
            "author_id": "pytest_user",
            "author_name": "Pytest User"
        }
        post = await client.post(f"{API_URL}/messages", json=payload)
        assert post.status_code == 200
        get = await client.get(f"{API_URL}/messages?limit=10")
        assert get.status_code == 200
        data = get.json()
        assert "messages" in data
        assert any(m["content"] == payload["content"] for m in data["messages"])

@pytest.mark.asyncio
async def test_logs_tail():
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_URL}/logs/latest.log?tail=10")
        assert resp.status_code == 200
        assert resp.text

@pytest.mark.asyncio
async def test_audit_entries():
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_URL}/audit?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

@pytest.mark.asyncio
async def test_tools_list_and_detail():
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_URL}/tools")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if data:
            tool_name = data[0]["name"]
            detail = await client.get(f"{API_URL}/tools/{tool_name}")
            assert detail.status_code == 200
            detail_data = detail.json()
            assert "name" in detail_data
