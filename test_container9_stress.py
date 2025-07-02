#!/usr/bin/env python3
"""Stress test on container 9 (port 8089) with rapid commands"""

import requests
import json
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

def send_command(base_url, token, command, channel_id, command_id):
    """Send a single command and return results"""
    headers = {"Authorization": f"Bearer {token}"}
    
    start_time = time.time()
    try:
        response = requests.post(
            f"{base_url}/v1/agent/interact",
            headers=headers,
            json={
                "message": command,
                "channel_id": channel_id
            },
            timeout=10
        )
        end_time = time.time()
        
        return {
            "command_id": command_id,
            "command": command,
            "status_code": response.status_code,
            "response": response.json() if response.status_code == 200 else response.text,
            "response_time": end_time - start_time,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        end_time = time.time()
        return {
            "command_id": command_id,
            "command": command,
            "status_code": -1,
            "response": str(e),
            "response_time": end_time - start_time,
            "timestamp": datetime.now().isoformat()
        }

def stress_test():
    base_url = "http://localhost:8089"
    channel_id = "api_0.0.0.0_8089"
    
    # Login first
    print(f"\n[{datetime.now().isoformat()}] Logging in to container 9...")
    login_response = requests.post(
        f"{base_url}/v1/auth/login",
        json={"username": "admin", "password": "ciris_admin_password"}
    )
    
    if login_response.status_code != 200:
        print(f"Login failed: {login_response.status_code} - {login_response.text}")
        return
    
    token = login_response.json()["access_token"]
    print(f"Login successful. Token: {token[:20]}...")
    
    # Commands for stress test
    commands = [
        "$speak test1",
        "$recall test2",
        "$memorize test3",
        "$ponder test4",
        "$observe test5"
    ]
    
    print(f"\n[{datetime.now().isoformat()}] Starting stress test with {len(commands)} rapid commands...")
    
    # Send all commands as fast as possible
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for i, cmd in enumerate(commands):
            future = executor.submit(send_command, base_url, token, cmd, channel_id, i+1)
            futures.append(future)
            # Very small delay to avoid overwhelming the server
            time.sleep(0.05)
        
        # Collect results
        results = []
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
    
    # Sort results by command_id to show in order
    results.sort(key=lambda x: x['command_id'])
    
    # Display results
    print(f"\n[{datetime.now().isoformat()}] Stress test completed. Results:")
    print("-" * 80)
    
    total_time = 0
    successful = 0
    failed = 0
    
    for result in results:
        print(f"\nCommand {result['command_id']}: {result['command']}")
        print(f"Timestamp: {result['timestamp']}")
        print(f"Status: {'SUCCESS' if result['status_code'] == 200 else 'FAILED'} ({result['status_code']})")
        print(f"Response time: {result['response_time']:.3f}s")
        
        if result['status_code'] == 200:
            successful += 1
            response_data = result['response'].get('data', result['response'])
            response_text = response_data.get('response', str(response_data))[:100]
            print(f"Response: {response_text}...")
        else:
            failed += 1
            print(f"Error: {result['response']}")
        
        total_time += result['response_time']
    
    # Summary statistics
    print("\n" + "=" * 80)
    print("STRESS TEST SUMMARY")
    print("=" * 80)
    print(f"Total commands: {len(commands)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Average response time: {total_time/len(commands):.3f}s")
    print(f"Total time: {total_time:.3f}s")
    
    # Check system health after stress test
    print(f"\n[{datetime.now().isoformat()}] Checking system health after stress test...")
    health_response = requests.get(
        f"{base_url}/v1/system/health",
        headers={"Authorization": "Bearer admin:ciris_admin_password"}
    )
    
    if health_response.status_code == 200:
        health = health_response.json()
        health_data = health.get('data', health)
        print(f"System Status: {health_data.get('status', 'unknown')}")
        print(f"Healthy Services: {health_data.get('healthy_services', 0)}/{health_data.get('total_services', 0)}")
        print(f"Container Uptime: {health_data.get('uptime', 'N/A')}")
    else:
        print(f"Health check failed: {health_response.status_code}")

if __name__ == "__main__":
    stress_test()