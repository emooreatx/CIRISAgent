#!/usr/bin/env python3
"""Test TASK_COMPLETE handler on container 8 (port 8088)"""

import requests
import json
import time
from datetime import datetime

def test_task_complete():
    base_url = "http://localhost:8088"
    
    # Login first
    print(f"\n[{datetime.now().isoformat()}] Logging in to container 8...")
    login_response = requests.post(
        f"{base_url}/v1/auth/login",
        json={"username": "admin", "password": "ciris_admin_password"}
    )
    
    if login_response.status_code != 200:
        print(f"Login failed: {login_response.status_code} - {login_response.text}")
        return
    
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"Login successful. Token: {token[:20]}...")
    
    # Test TASK_COMPLETE commands
    test_cases = [
        "$task_complete Successfully completed analysis",
        "$task_complete All tests passed"
    ]
    
    for i, command in enumerate(test_cases, 1):
        print(f"\n[{datetime.now().isoformat()}] Test {i}: {command}")
        
        start_time = time.time()
        response = requests.post(
            f"{base_url}/v1/agent/interact",
            headers=headers,
            json={
                "message": command,
                "channel_id": "api_0.0.0.0_8088"
            }
        )
        end_time = time.time()
        
        if response.status_code == 200:
            result = response.json()
            print(f"Status: SUCCESS")
            print(f"Response time: {end_time - start_time:.3f}s")
            print(f"Response: {json.dumps(result, indent=2)}")
            
            # Check if it triggered task scheduling
            if "task" in result.get("response", "").lower() or "schedule" in result.get("response", "").lower():
                print("✓ Task scheduling appears to be triggered")
            else:
                print("⚠ Task scheduling may not have been triggered")
        else:
            print(f"Status: FAILED ({response.status_code})")
            print(f"Error: {response.text}")
    
    # Check system health after tests
    print(f"\n[{datetime.now().isoformat()}] Checking system health...")
    health_response = requests.get(
        f"{base_url}/v1/system/health",
        headers={"Authorization": "Bearer admin:ciris_admin_password"}
    )
    
    if health_response.status_code == 200:
        health = health_response.json()
        # API returns data wrapper
        health_data = health.get('data', health)
        print(f"System Status: {health_data.get('status', 'unknown')}")
        print(f"Healthy Services: {health_data.get('healthy_services', 0)}/{health_data.get('total_services', 0)}")
    else:
        print(f"Health check failed: {health_response.status_code}")

if __name__ == "__main__":
    test_task_complete()