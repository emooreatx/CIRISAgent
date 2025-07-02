#!/usr/bin/env python3
"""Simple test for channel isolation"""

import requests
import json
from datetime import datetime

def test_simple_isolation():
    """Test basic channel isolation"""
    
    # Container 3 (port 8083)
    port = 8083
    base_url = f"http://localhost:{port}"
    
    # Login as admin
    print(f"\n[Container {port}] Logging in as admin...")
    login_resp = requests.post(f"{base_url}/v1/auth/login", 
                              json={"username": "admin", "password": "ciris_admin_password"})
    if login_resp.status_code != 200:
        print(f"Login failed: {login_resp.status_code}")
        print(login_resp.text)
        return
    
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create two different channels
    channel_a = "api_test_channel_a"
    channel_b = "api_test_channel_b"
    
    print(f"\n=== Testing Channel Isolation ===")
    print(f"Channel A: {channel_a}")
    print(f"Channel B: {channel_b}")
    
    # Store data in channel A
    print(f"\n[1] Storing data in Channel A...")
    resp = requests.post(f"{base_url}/v1/agent/interact",
                        headers=headers,
                        json={"message": "$memorize test_secret_data CONCEPT LOCAL", 
                              "channel_id": channel_a})
    print(f"Response: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"Content: {data.get('content', 'No content')}")
    else:
        print(f"Error: {resp.text}")
    
    # Try to recall from channel A (should work)
    print(f"\n[2] Recalling from Channel A (should find it)...")
    resp = requests.post(f"{base_url}/v1/agent/interact",
                        headers=headers,
                        json={"message": "$recall test_secret_data CONCEPT LOCAL", 
                              "channel_id": channel_a})
    print(f"Response: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        content = data.get('content', 'No content')
        print(f"Content: {content}")
        if "test_secret_data" in content or "found" in content.lower():
            print("✅ SUCCESS: Data found in correct channel")
        else:
            print("❌ UNEXPECTED: Data not found in correct channel")
    
    # Try to recall from channel B (should NOT find it)
    print(f"\n[3] Recalling from Channel B (should NOT find it)...")
    resp = requests.post(f"{base_url}/v1/agent/interact",
                        headers=headers,
                        json={"message": "$recall test_secret_data CONCEPT LOCAL", 
                              "channel_id": channel_b})
    print(f"Response: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        content = data.get('content', 'No content')
        print(f"Content: {content}")
        if "test_secret_data" in content or "found" in content.lower():
            print("❌ SECURITY ISSUE: Data leaked across channels!")
        else:
            print("✅ SUCCESS: Data properly isolated between channels")
    
    print("\n=== Summary ===")
    print("Channel isolation test completed.")
    print("Expected behavior:")
    print("- Data stored in one channel should NOT be accessible from another")
    print("- This prevents data leakage between different users/sessions")

if __name__ == "__main__":
    test_simple_isolation()