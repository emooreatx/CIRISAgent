#!/usr/bin/env python3
"""Single command benchmark to test basic performance."""

import requests
import time
import json

# Test Container 6
print("Testing Container 6 (Port 8086)")
print("-" * 40)

# Login
login_start = time.time()
response = requests.post(
    "http://localhost:8086/v1/auth/login",
    json={"username": "admin", "password": "ciris_admin_password"}
)
login_time = time.time() - login_start

if response.status_code == 200:
    token = response.json()["access_token"]
    print(f"✓ Login successful in {login_time:.3f}s")
    
    # Test single SPEAK command
    headers = {"Authorization": f"Bearer {token}"}
    
    print("\nTesting SPEAK command:")
    speak_start = time.time()
    try:
        response = requests.post(
            "http://localhost:8086/v1/agent/interact",
            headers=headers,
            json={"message": "$speak Hello world", "channel_id": "api_test"},
            timeout=30
        )
        speak_time = time.time() - speak_start
        
        if response.status_code == 200:
            print(f"✓ SPEAK completed in {speak_time:.3f}s")
            print(f"Response: {response.json()['data']['response'][:100]}...")
        else:
            print(f"✗ SPEAK failed: {response.status_code}")
    except Exception as e:
        print(f"✗ SPEAK error: {e}")
    
    # Wait a bit
    time.sleep(2)
    
    # Test single RECALL command
    print("\nTesting RECALL command:")
    recall_start = time.time()
    try:
        response = requests.post(
            "http://localhost:8086/v1/agent/interact",
            headers=headers,
            json={"message": "$recall test", "channel_id": "api_test"},
            timeout=30
        )
        recall_time = time.time() - recall_start
        
        if response.status_code == 200:
            print(f"✓ RECALL completed in {recall_time:.3f}s")
            print(f"Response: {response.json()['data']['response'][:100]}...")
        else:
            print(f"✗ RECALL failed: {response.status_code}")
    except Exception as e:
        print(f"✗ RECALL error: {e}")
        
    # Check health
    print("\nChecking system health:")
    try:
        response = requests.get(
            "http://localhost:8086/v1/system/health",
            headers=headers
        )
        if response.status_code == 200:
            health = response.json()["data"]
            print(f"Status: {health['status']}")
            print(f"Uptime: {health['uptime_seconds']:.0f}s")
            print(f"Services healthy: {sum(s['healthy'] for s in health['services'].values())}/{len(health['services'])}")
    except Exception as e:
        print(f"Health check error: {e}")
else:
    print(f"✗ Login failed: {response.status_code}")

print("\n" + "=" * 40)

# Test Container 8 
print("\nTesting Container 8 (Port 8088)")
print("-" * 40)

# Login
login_start = time.time()
response = requests.post(
    "http://localhost:8088/v1/auth/login",
    json={"username": "admin", "password": "ciris_admin_password"}
)
login_time = time.time() - login_start

if response.status_code == 200:
    token = response.json()["access_token"]
    print(f"✓ Login successful in {login_time:.3f}s")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Send 5 rapid commands
    print("\nSending 5 rapid commands:")
    total_start = time.time()
    times = []
    
    for i in range(5):
        cmd_start = time.time()
        try:
            response = requests.post(
                "http://localhost:8088/v1/agent/interact",
                headers=headers,
                json={"message": f"$speak Test {i}", "channel_id": "api_test"},
                timeout=30
            )
            cmd_time = time.time() - cmd_start
            times.append(cmd_time)
            
            if response.status_code == 200:
                print(f"  [{i+1}] ✓ {cmd_time:.3f}s")
            else:
                print(f"  [{i+1}] ✗ Failed: {response.status_code}")
        except Exception as e:
            print(f"  [{i+1}] ✗ Error: {e}")
    
    total_time = time.time() - total_start
    
    if times:
        print(f"\nTotal time: {total_time:.2f}s")
        print(f"Average: {sum(times)/len(times):.3f}s per command")
        print(f"Throughput: {len(times)/total_time:.2f} commands/second")
else:
    print(f"✗ Login failed: {response.status_code}")

print("\nDone!")