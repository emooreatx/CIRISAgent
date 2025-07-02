#!/usr/bin/env python3
"""Simple test to verify channel extraction in mock LLM."""

import asyncio
import aiohttp
import json

async def test_single_container():
    """Test channel extraction on a single container."""
    port = 8080
    base_url = f"http://localhost:{port}"
    
    async with aiohttp.ClientSession() as session:
        # Login
        print("1. Logging in...")
        async with session.post(f"{base_url}/v1/auth/login", json={
            "username": "admin",
            "password": "ciris_admin_password"
        }) as resp:
            auth = await resp.json()
            token = auth["access_token"]
            print(f"   Got token: {token[:20]}...")
        
        # Send test message
        headers = {"Authorization": f"Bearer {token}"}
        test_channel = f"api_test_{port}_channel_test"
        
        print(f"\n2. Sending message with channel: {test_channel}")
        async with session.post(
            f"{base_url}/v1/agent/interact",
            json={
                "message": "$speak Channel extraction test", 
                "channel_id": test_channel
            },
            headers=headers
        ) as resp:
            result = await resp.json()
            print(f"   Response: {json.dumps(result, indent=2)}")
        
        # Wait a bit for processing
        print("\n3. Waiting 5 seconds for processing...")
        await asyncio.sleep(5)
        
        # Check conversation history
        print("\n4. Checking conversation history...")
        async with session.get(
            f"{base_url}/v1/agent/conversation/{test_channel}",
            headers=headers
        ) as resp:
            if resp.status == 200:
                history = await resp.json()
                print(f"   Found {len(history.get('data', {}).get('messages', []))} messages")
                for msg in history.get('data', {}).get('messages', [])[-3:]:
                    print(f"   - {msg.get('role', 'unknown')}: {msg.get('content', '')[:100]}...")
            else:
                print(f"   Error: {resp.status}")

if __name__ == "__main__":
    asyncio.run(test_single_container())