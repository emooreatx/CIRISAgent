#!/usr/bin/env python3
import asyncio
import aiohttp
import json

async def test_api_message():
    data = {
        "message_id": "test-manual-123",
        "author_id": "test_user",
        "author_name": "Test User",
        "content": "$speak Hello CIRIS from manual test!",
        "channel_id": "test_manual_channel"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://localhost:8080/api/v1/message",
            json=data,
            headers={"Content-Type": "application/json"}
        ) as response:
            result = await response.json()
            print(f"Response status: {response.status}")
            print(f"Response body: {json.dumps(result, indent=2)}")
            
    # Wait and check for messages
    await asyncio.sleep(2)
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"http://localhost:8080/api/v1/messages/test_manual_channel?limit=10"
        ) as response:
            result = await response.json()
            print(f"\nMessages in channel:")
            for msg in result.get("messages", []):
                print(f"  - {msg['author_name']}: {msg['content'][:50]}...")

if __name__ == "__main__":
    asyncio.run(test_api_message())