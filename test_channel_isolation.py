#!/usr/bin/env python3
"""Test channel isolation between different auth contexts"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime
import uuid

BASE_URL_TEMPLATE = "http://localhost:{}"

async def login(session, port, username, password):
    """Login and get access token"""
    url = f"{BASE_URL_TEMPLATE.format(port)}/v1/auth/login"
    async with session.post(url, json={"username": username, "password": password}) as resp:
        if resp.status == 200:
            data = await resp.json()
            return data.get("access_token")
        else:
            print(f"Login failed on port {port}: {resp.status}")
            text = await resp.text()
            print(f"Response: {text}")
            return None

async def send_message(session, port, token, message, channel_id=None):
    """Send a message via the interact endpoint"""
    # Generate unique channel ID for this session if not provided
    if not channel_id:
        channel_id = f"api_test_{port}_{uuid.uuid4().hex[:8]}"
    
    url = f"{BASE_URL_TEMPLATE.format(port)}/v1/agent/interact"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "message": message,
        "channel_id": channel_id
    }
    
    print(f"\n[Port {port}] Sending to channel {channel_id}: {message}")
    
    async with session.post(url, json=payload, headers=headers) as resp:
        if resp.status == 200:
            data = await resp.json()
            print(f"[Port {port}] Response: {data.get('content', 'No content')}")
            return data, channel_id
        else:
            print(f"[Port {port}] Message failed: {resp.status}")
            text = await resp.text()
            print(f"Response: {text}")
            return None, channel_id

async def test_container(session, port, test_name):
    """Test a single container"""
    print(f"\n{'='*60}")
    print(f"Testing {test_name} on port {port}")
    print(f"{'='*60}")
    
    # Login as admin
    token = await login(session, port, "admin", "ciris_admin_password")
    if not token:
        print(f"Failed to login to port {port}")
        return None
    
    return token

async def test_channel_isolation():
    """Test channel isolation between different auth contexts"""
    
    async with aiohttp.ClientSession() as session:
        # Container 3 tests
        print("\n" + "="*80)
        print("PHASE 1: Container 3 (Port 8083) - Create Secret Data")
        print("="*80)
        
        token3 = await test_container(session, 8083, "Container 3")
        if not token3:
            return
        
        # Create two different channels for admin user
        channel3_a = f"api_admin_channel_a_{uuid.uuid4().hex[:8]}"
        channel3_b = f"api_admin_channel_b_{uuid.uuid4().hex[:8]}"
        
        # Store secret in channel A
        print(f"\n[Container 3] Testing channel isolation with two channels:")
        print(f"Channel A: {channel3_a}")
        print(f"Channel B: {channel3_b}")
        
        # Memorize in channel A
        await send_message(session, 8083, token3, 
                          "$memorize admin_secret_a CONCEPT LOCAL", 
                          channel3_a)
        
        # Try to recall from channel A (should work)
        await send_message(session, 8083, token3, 
                          "$recall admin_secret_a CONCEPT LOCAL", 
                          channel3_a)
        
        # Try to recall from channel B (should NOT find it if channels are isolated)
        await send_message(session, 8083, token3, 
                          "$recall admin_secret_a CONCEPT LOCAL", 
                          channel3_b)
        
        # Container 4 tests
        print("\n" + "="*80)
        print("PHASE 2: Container 4 (Port 8084) - Cross-Container Test")
        print("="*80)
        
        token4 = await test_container(session, 8084, "Container 4")
        if not token4:
            return
        
        # Try to access data from Container 3's channels
        print(f"\n[Container 4] Attempting to access Container 3's data:")
        
        # Try with the exact channel ID from container 3
        await send_message(session, 8084, token4, 
                          "$recall admin_secret_a CONCEPT LOCAL", 
                          channel3_a)
        
        # Create a new channel and memorize different data
        channel4 = f"api_admin_channel_c_{uuid.uuid4().hex[:8]}"
        await send_message(session, 8084, token4, 
                          "$memorize container4_data CONCEPT LOCAL", 
                          channel4)
        
        # Verify we can recall our own data
        await send_message(session, 8084, token4, 
                          "$recall container4_data CONCEPT LOCAL", 
                          channel4)
        
        # Advanced isolation tests
        print("\n" + "="*80)
        print("PHASE 3: Advanced Isolation Tests")
        print("="*80)
        
        # Test 1: Same user, different channels in same container
        print("\n[Test 1] Same user, different channels, same container:")
        channel_test1 = f"api_test_isolation_1_{uuid.uuid4().hex[:8]}"
        channel_test2 = f"api_test_isolation_2_{uuid.uuid4().hex[:8]}"
        
        await send_message(session, 8083, token3, 
                          "$memorize test_data_1 CONCEPT LOCAL", 
                          channel_test1)
        
        # Should find in correct channel
        await send_message(session, 8083, token3, 
                          "$recall test_data_1 CONCEPT LOCAL", 
                          channel_test1)
        
        # Should NOT find in different channel
        await send_message(session, 8083, token3, 
                          "$recall test_data_1 CONCEPT LOCAL", 
                          channel_test2)
        
        # Test 2: Try to list all memories (check if filtered by channel)
        print("\n[Test 2] Attempting to list all memories:")
        await send_message(session, 8083, token3, 
                          "$recall * CONCEPT LOCAL",  # Wildcard attempt
                          channel_test1)
        
        # Summary report
        print("\n" + "="*80)
        print("CHANNEL ISOLATION TEST SUMMARY")
        print("="*80)
        print("""
Expected Results for Proper Channel Isolation:
1. ✅ Data stored in one channel should NOT be accessible from another channel
2. ✅ Same user with different channels should have isolated data
3. ✅ Cross-container access should not leak channel data
4. ✅ Wildcard queries should still respect channel boundaries

Security Implications:
- If channels are NOT isolated: Critical security vulnerability
- If channels ARE isolated: System is working as designed
- Channel IDs should act as security boundaries for user data
""")

if __name__ == "__main__":
    asyncio.run(test_channel_isolation())