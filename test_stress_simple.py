#!/usr/bin/env python3
"""Simple stress test for containers"""

import requests
import time
import threading
from datetime import datetime

def send_command(port, token, command, results, index):
    """Send a single command and store result"""
    url = f"http://localhost:{port}/v1/agent/interact"
    headers = {"Authorization": f"Bearer {token}"}
    
    start_time = time.time()
    try:
        response = requests.post(
            url,
            headers=headers,
            json={
                "message": command,
                "channel_id": f"api_0.0.0.0_{port}"
            },
            timeout=45
        )
        end_time = time.time()
        
        results[index] = {
            "command": command,
            "status": response.status_code,
            "response": response.json() if response.status_code == 200 else response.text,
            "time": end_time - start_time,
            "success": response.status_code == 200
        }
    except Exception as e:
        end_time = time.time()
        results[index] = {
            "command": command,
            "status": -1,
            "response": str(e),
            "time": end_time - start_time,
            "success": False
        }

def stress_test_port(port):
    """Run stress test on a specific port"""
    print(f"\n{'='*60}")
    print(f"Stress Testing Container on Port {port}")
    print(f"{'='*60}")
    
    # Check health first
    try:
        health = requests.get(
            f"http://localhost:{port}/v1/system/health",
            headers={"Authorization": "Bearer admin:ciris_admin_password"},
            timeout=5
        )
        if health.status_code != 200:
            print(f"✗ Container unhealthy, skipping")
            return
    except:
        print(f"✗ Container not responding, skipping")
        return
    
    # Login
    try:
        login = requests.post(
            f"http://localhost:{port}/v1/auth/login",
            json={"username": "admin", "password": "ciris_admin_password"},
            timeout=5
        )
        token = login.json()["access_token"]
        print(f"✓ Login successful")
    except Exception as e:
        print(f"✗ Login failed: {e}")
        return
    
    # Commands to test
    commands = [
        "$speak Stress test message 1",
        "$recall test_memory",
        "$memorize stress_test_data",
        "$ponder What is happening?",
        "$observe Monitoring stress test"
    ]
    
    print(f"\nSending {len(commands)} commands rapidly...")
    
    # Send commands using threads
    threads = []
    results = [None] * len(commands)
    
    start_time = time.time()
    for i, cmd in enumerate(commands):
        thread = threading.Thread(target=send_command, args=(port, token, cmd, results, i))
        threads.append(thread)
        thread.start()
        time.sleep(0.1)  # Small delay between starts
    
    # Wait for all threads
    for thread in threads:
        thread.join(timeout=60)
    
    total_time = time.time() - start_time
    
    # Analyze results
    print(f"\nResults after {total_time:.2f}s:")
    print("-" * 60)
    
    successful = sum(1 for r in results if r and r['success'])
    failed = len(results) - successful
    
    for i, result in enumerate(results):
        if result:
            status = "✓" if result['success'] else "✗"
            print(f"{status} Command {i+1}: {result['command'][:30]}...")
            print(f"   Status: {result['status']}, Time: {result['time']:.2f}s")
            if result['success']:
                data = result['response'].get('data', {})
                response_text = data.get('response', '')[:80]
                print(f"   Response: {response_text}...")
        else:
            print(f"✗ Command {i+1}: No result (thread timeout)")
    
    print(f"\nSummary:")
    print(f"- Successful: {successful}/{len(commands)}")
    print(f"- Failed: {failed}/{len(commands)}")
    print(f"- Total time: {total_time:.2f}s")
    print(f"- Avg response time: {sum(r['time'] for r in results if r) / len([r for r in results if r]):.2f}s")
    
    # Check health after stress
    try:
        health = requests.get(
            f"http://localhost:{port}/v1/system/health",
            headers={"Authorization": "Bearer admin:ciris_admin_password"},
            timeout=5
        )
        if health.status_code == 200:
            health_data = health.json().get('data', {})
            print(f"\n✓ Container still healthy after stress test")
            print(f"  Services: {health_data.get('healthy_services', 0)}/{health_data.get('total_services', 0)}")
        else:
            print(f"\n⚠ Container health degraded after stress test")
    except:
        print(f"\n✗ Container not responding after stress test")

def main():
    """Run stress tests on available containers"""
    print("Container Stress Test")
    print("="*60)
    
    # Test specific containers
    test_ports = [8080, 8081, 8082]  # Test first 3 containers
    
    for port in test_ports:
        stress_test_port(port)
        time.sleep(2)  # Brief pause between containers

if __name__ == "__main__":
    main()