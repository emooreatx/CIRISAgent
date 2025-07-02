#!/usr/bin/env python3
"""Inspect what the mock LLM actually receives"""

import requests
import json
import time

def test_with_logging(port, command):
    """Test a command and check logs"""
    print(f"\nTesting: {command}")
    
    # Login
    login_url = f"http://localhost:{port}/v1/auth/login"
    response = requests.post(login_url, json={"username": "admin", "password": "ciris_admin_password"})
    token = response.json()["access_token"]
    
    # Clear logs timestamp
    timestamp_before = time.time()
    
    # Send command  
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        f"http://localhost:{port}/v1/agent/interact",
        headers=headers,
        json={"message": command}
    )
    
    print(f"Response: {response.json()['data']['response']}")
    
    # Wait a bit for logs
    time.sleep(2)
    
    return timestamp_before

# Test each command and note the timestamp
print("Testing Mock LLM command recognition...")

# Test speak (should work)
ts1 = test_with_logging(8086, "$speak Hello from test")

# Test defer (problematic)  
ts2 = test_with_logging(8086, "$defer Need more info")

# Test with explicit context prefix
ts3 = test_with_logging(8086, "user_input:$defer Testing defer")

# Test forced action format
ts4 = test_with_logging(8086, "forced_action:defer action_params:Test defer via forced action")

print("\nCheck container logs after timestamp:", int(ts1))