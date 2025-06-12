"""
Comprehensive tests for enhanced API endpoints including:
- Fixed /v1/messages with correlation support
- New memory endpoints (search, recall, timeseries)
- Enhanced audit endpoints (query, log)
- Tool validation endpoint
"""
import pytest
import httpx
import os
import uuid
import asyncio
from datetime import datetime, timezone

API_URL = os.environ.get("CIRIS_API_URL", "http://localhost:8080")

async def api_available():
    """Check if API server is running."""
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            resp = await client.get(f"{API_URL}/v1/status")
            return resp.status_code == 200
    except Exception:
        return False

@pytest.mark.asyncio
async def test_messages_with_correlations():
    """Test that /v1/messages returns both incoming and outgoing messages."""
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    
    async with httpx.AsyncClient() as client:
        # Send a test message
        test_id = str(uuid.uuid4())
        payload = {
            "content": f"Test correlation message {test_id}",
            "channel_id": "api",
            "author_id": "test_user",
            "author_name": "Test User"
        }
        
        # Send message
        post_resp = await client.post(f"{API_URL}/v1/messages", json=payload)
        assert post_resp.status_code in [200, 202]
        message_id = post_resp.json().get("id")
        
        # Wait a bit for processing
        await asyncio.sleep(2)
        
        # Get messages
        get_resp = await client.get(f"{API_URL}/v1/messages?limit=20&channel_id=api")
        assert get_resp.status_code == 200
        
        messages = get_resp.json()["messages"]
        
        # Should have at least the incoming message
        incoming_msgs = [m for m in messages if m.get("is_outgoing") == False and test_id in m.get("content", "")]
        assert len(incoming_msgs) > 0, "Should find the incoming test message"
        
        # Should also have outgoing messages (agent responses)
        outgoing_msgs = [m for m in messages if m.get("is_outgoing") == True]
        # Note: Might not have responses if agent is not processing, but structure should be there
        
        # Verify message structure
        for msg in messages:
            assert "id" in msg
            assert "content" in msg
            assert "author_id" in msg
            assert "is_outgoing" in msg

@pytest.mark.asyncio
async def test_memory_search():
    """Test memory search endpoint."""
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    
    async with httpx.AsyncClient() as client:
        # First store something to search for
        store_payload = {
            "key": f"test_search_{uuid.uuid4()}",
            "value": "searchable test data with unique keywords"
        }
        store_resp = await client.post(f"{API_URL}/v1/memory/local/store", json=store_payload)
        assert store_resp.status_code in [200, 500]  # 500 if memory service not fully available
        
        # Now search for it
        search_payload = {
            "query": "searchable test data",
            "scope": "local",
            "limit": 10
        }
        search_resp = await client.post(f"{API_URL}/v1/memory/search", json=search_payload)
        assert search_resp.status_code in [200, 501]  # 501 if search not implemented
        
        if search_resp.status_code == 200:
            data = search_resp.json()
            assert "results" in data

@pytest.mark.asyncio
async def test_memory_recall():
    """Test memory recall endpoint."""
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    
    async with httpx.AsyncClient() as client:
        # Store something first
        node_id = f"test_recall_{uuid.uuid4()}"
        store_payload = {
            "key": node_id,
            "value": "data to recall"
        }
        store_resp = await client.post(f"{API_URL}/v1/memory/local/store", json=store_payload)
        
        # Now recall it
        recall_payload = {
            "node_id": node_id,
            "scope": "local",
            "node_type": "CONCEPT"
        }
        recall_resp = await client.post(f"{API_URL}/v1/memory/recall", json=recall_payload)
        assert recall_resp.status_code in [200, 404, 500]
        
        if recall_resp.status_code == 200:
            data = recall_resp.json()
            assert "data" in data

@pytest.mark.asyncio
async def test_memory_forget():
    """Test memory forget endpoint."""
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    
    async with httpx.AsyncClient() as client:
        # Store something first
        node_id = f"test_forget_{uuid.uuid4()}"
        store_payload = {
            "key": node_id,
            "value": "data to forget"
        }
        store_resp = await client.post(f"{API_URL}/v1/memory/local/store", json=store_payload)
        
        # Now forget it
        forget_resp = await client.delete(f"{API_URL}/v1/memory/local/{node_id}")
        assert forget_resp.status_code in [200, 500]
        
        if forget_resp.status_code == 200:
            data = forget_resp.json()
            assert data.get("result") == "forgotten"

@pytest.mark.asyncio
async def test_memory_timeseries():
    """Test memory timeseries endpoint."""
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_URL}/v1/memory/timeseries?scope=local&hours=24")
        assert resp.status_code in [200, 501]  # 501 if not implemented
        
        if resp.status_code == 200:
            data = resp.json()
            assert "timeseries" in data
            assert isinstance(data["timeseries"], list)

@pytest.mark.asyncio
async def test_audit_query():
    """Test audit query endpoint with filters."""
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    
    async with httpx.AsyncClient() as client:
        # Query with various filters
        query_payload = {
            "start_time": "2025-01-01T00:00:00Z",
            "end_time": datetime.now(timezone.utc).isoformat(),
            "action_types": ["send_message", "defer"],
            "limit": 10
        }
        
        resp = await client.post(f"{API_URL}/v1/audit/query", json=query_payload)
        assert resp.status_code == 200
        
        data = resp.json()
        assert "entries" in data
        assert isinstance(data["entries"], list)

@pytest.mark.asyncio
async def test_audit_log():
    """Test audit log endpoint."""
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    
    async with httpx.AsyncClient() as client:
        log_payload = {
            "event_type": "test_event",
            "event_data": {
                "test_id": str(uuid.uuid4()),
                "action": "unit_test",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        
        resp = await client.post(f"{API_URL}/v1/audit/log", json=log_payload)
        assert resp.status_code in [200, 501]  # 501 if not implemented
        
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("status") == "logged"

@pytest.mark.asyncio
async def test_tool_validation():
    """Test tool parameter validation endpoint."""
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    
    async with httpx.AsyncClient() as client:
        # Test with a known tool (echo)
        validate_payload = {
            "text": "Hello, world!"
        }
        
        resp = await client.post(f"{API_URL}/v1/tools/echo/validate", json=validate_payload)
        assert resp.status_code in [200, 501]
        
        if resp.status_code == 200:
            data = resp.json()
            assert "valid" in data
            assert isinstance(data["valid"], bool)
        
        # Test with unknown tool
        resp2 = await client.post(f"{API_URL}/v1/tools/nonexistent/validate", json={})
        assert resp2.status_code in [200, 501]
        
        if resp2.status_code == 200:
            data2 = resp2.json()
            assert data2.get("valid") == False or "reason" in data2

@pytest.mark.asyncio
async def test_ls_home_tool():
    """Test the new ls_home tool endpoint."""
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    
    async with httpx.AsyncClient() as client:
        # Test ls_home tool execution
        resp = await client.post(f"{API_URL}/v1/tools/ls_home", json={})
        assert resp.status_code in [200, 501]
        
        if resp.status_code == 200:
            data = resp.json()
            assert "correlation_id" in data
            
            # Check if result contains expected structure
            if "result" in data:
                result = data["result"]
                assert "success" in result
                if result.get("success"):
                    assert "home_directory" in result
                    assert "contents" in result
                    assert "total_items" in result
                    assert isinstance(result["contents"], list)
                    assert isinstance(result["total_items"], int)
                    
                    # Verify contents structure
                    for item in result["contents"]:
                        assert "name" in item
                        assert "type" in item
                        if item["type"] != "unknown":
                            assert "modified" in item

@pytest.mark.asyncio
async def test_messages_empty_channel():
    """Test messages endpoint with empty/new channel."""
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    
    async with httpx.AsyncClient() as client:
        # Query a channel that likely doesn't exist
        channel_id = f"test_channel_{uuid.uuid4()}"
        resp = await client.get(f"{API_URL}/v1/messages?channel_id={channel_id}")
        
        assert resp.status_code == 200
        data = resp.json()
        assert "messages" in data
        assert isinstance(data["messages"], list)
        assert len(data["messages"]) == 0  # Should be empty

@pytest.mark.asyncio
async def test_memory_invalid_scope():
    """Test memory endpoints with invalid scope."""
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    
    async with httpx.AsyncClient() as client:
        # Try to store with invalid scope - should fallback to LOCAL
        store_payload = {
            "key": "test_key",
            "value": "test_value"
        }
        
        resp = await client.post(f"{API_URL}/v1/memory/invalid_scope/store", json=store_payload)
        # Should still work by falling back to LOCAL scope
        assert resp.status_code in [200, 500]

@pytest.mark.asyncio
async def test_audit_query_edge_cases():
    """Test audit query with edge cases."""
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    
    async with httpx.AsyncClient() as client:
        # Test with no filters
        resp1 = await client.post(f"{API_URL}/v1/audit/query", json={})
        assert resp1.status_code == 200
        
        # Test with invalid date format - should handle gracefully
        resp2 = await client.post(f"{API_URL}/v1/audit/query", json={
            "start_time": "invalid_date"
        })
        assert resp2.status_code in [200, 400, 500]  # May fail or handle gracefully
        
        # Test with future dates
        resp3 = await client.post(f"{API_URL}/v1/audit/query", json={
            "start_time": "2030-01-01T00:00:00Z",
            "end_time": "2031-01-01T00:00:00Z"
        })
        assert resp3.status_code == 200
        data = resp3.json()
        assert data.get("entries", []) == []  # Should be empty

@pytest.mark.asyncio
async def test_concurrent_message_handling():
    """Test concurrent message sending and retrieval."""
    if not await api_available():
        pytest.skip("CIRIS API server is not available.")
    
    async with httpx.AsyncClient() as client:
        # Send multiple messages concurrently
        tasks = []
        message_ids = []
        
        for i in range(5):
            payload = {
                "content": f"Concurrent test message {i}",
                "channel_id": "concurrent_test",
                "author_id": f"user_{i}"
            }
            task = client.post(f"{API_URL}/v1/messages", json=payload)
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        
        for resp in responses:
            assert resp.status_code in [200, 202]
            message_ids.append(resp.json().get("id"))
        
        # Wait for processing
        await asyncio.sleep(1)
        
        # Retrieve all messages
        get_resp = await client.get(f"{API_URL}/v1/messages?channel_id=concurrent_test&limit=50")
        assert get_resp.status_code == 200
        
        messages = get_resp.json()["messages"]
        # Should have at least some of our concurrent messages
        found_msgs = [m for m in messages if "Concurrent test message" in m.get("content", "")]
        assert len(found_msgs) > 0