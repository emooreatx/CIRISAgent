#!/usr/bin/env python3
"""Simplified performance benchmark for CIRIS API."""

import requests
import time
import statistics
import json

def login(base_url):
    """Login and get token."""
    response = requests.post(
        f"{base_url}/v1/auth/login",
        json={"username": "admin", "password": "ciris_admin_password"}
    )
    return response.json()["access_token"]

def send_command(base_url, token, command, channel_id):
    """Send command and measure response time."""
    headers = {"Authorization": f"Bearer {token}"}
    start = time.time()
    
    response = requests.post(
        f"{base_url}/v1/agent/interact",
        headers=headers,
        json={"message": command, "channel_id": channel_id},
        timeout=10
    )
    
    elapsed = time.time() - start
    success = response.status_code == 200
    return elapsed, success

def benchmark_handler(base_url, token, handler, count=10):
    """Benchmark a specific handler."""
    channel_id = f"api_benchmark_{base_url.split(':')[-1]}"
    
    commands = {
        "SPEAK": "$speak Hello, this is a test message",
        "RECALL": "$recall test",
        "MEMORIZE": "$memorize test_key_{} Test value {}"
    }
    
    times = []
    successes = 0
    
    print(f"\nBenchmarking {handler} ({count} requests):")
    
    for i in range(count):
        cmd = commands[handler]
        if "{}" in cmd:
            cmd = cmd.format(i, i)
            
        try:
            elapsed, success = send_command(base_url, token, cmd, channel_id)
            if success:
                times.append(elapsed)
                successes += 1
                print(f"  [{i+1}] ✓ {elapsed:.3f}s")
            else:
                print(f"  [{i+1}] ✗ Failed")
        except Exception as e:
            print(f"  [{i+1}] ✗ Error: {e}")
    
    if times:
        return {
            "handler": handler,
            "success_rate": successes / count * 100,
            "avg_time": statistics.mean(times),
            "min_time": min(times),
            "max_time": max(times)
        }
    return None

def throughput_test(base_url, token, count=20):
    """Test rapid command throughput."""
    channel_id = f"api_benchmark_{base_url.split(':')[-1]}"
    
    print(f"\nThroughput test ({count} rapid commands):")
    
    start = time.time()
    successes = 0
    times = []
    
    for i in range(count):
        try:
            elapsed, success = send_command(
                base_url, token, 
                f"$speak Throughput test {i}", 
                channel_id
            )
            if success:
                successes += 1
                times.append(elapsed)
            print(f"  [{i+1}] {'✓' if success else '✗'} {elapsed:.3f}s")
        except Exception as e:
            print(f"  [{i+1}] ✗ Error: {e}")
    
    total_time = time.time() - start
    
    return {
        "total_commands": count,
        "successful": successes,
        "total_time": total_time,
        "throughput": successes / total_time,
        "avg_response": statistics.mean(times) if times else 0
    }

def get_health(base_url, token):
    """Get system health."""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{base_url}/v1/system/health", headers=headers)
    return response.json()["data"]

print("=" * 60)
print("CIRIS Performance Benchmark")
print("=" * 60)

# Container 6 - Handler benchmarks
print("\n🔧 CONTAINER 6 (Port 8086) - Handler Performance")
print("-" * 60)

base_url6 = "http://localhost:8086"
token6 = login(base_url6)
print("✓ Logged in to Container 6")

# Get initial health
health_before_6 = get_health(base_url6, token6)
print(f"Status: {health_before_6['status']}, Uptime: {health_before_6['uptime_seconds']:.0f}s")

# Benchmark each handler
results_6 = []
for handler in ["SPEAK", "RECALL", "MEMORIZE"]:
    result = benchmark_handler(base_url6, token6, handler, count=10)
    if result:
        results_6.append(result)
    time.sleep(0.5)  # Small delay between handlers

# Get final health
health_after_6 = get_health(base_url6, token6)

print("\n📊 Container 6 Summary:")
for r in results_6:
    print(f"\n{r['handler']}:")
    print(f"  Success Rate: {r['success_rate']:.0f}%")
    print(f"  Avg Response: {r['avg_time']:.3f}s")
    print(f"  Min/Max: {r['min_time']:.3f}s / {r['max_time']:.3f}s")

print(f"\nUptime: {health_after_6['uptime_seconds']:.0f}s")

# Container 8 - Throughput test
print("\n\n🔧 CONTAINER 8 (Port 8088) - Throughput Test")
print("-" * 60)

base_url8 = "http://localhost:8088"
token8 = login(base_url8)
print("✓ Logged in to Container 8")

# Get initial health
health_before_8 = get_health(base_url8, token8)
print(f"Status: {health_before_8['status']}, Uptime: {health_before_8['uptime_seconds']:.0f}s")

# Run throughput test
throughput = throughput_test(base_url8, token8, count=20)

# Get final health
health_after_8 = get_health(base_url8, token8)

print("\n📊 Container 8 Summary:")
print(f"Success Rate: {throughput['successful']}/{throughput['total_commands']} ({throughput['successful']/throughput['total_commands']*100:.0f}%)")
print(f"Total Time: {throughput['total_time']:.2f}s")
print(f"Throughput: {throughput['throughput']:.2f} commands/second")
print(f"Avg Response: {throughput['avg_response']:.3f}s")
print(f"\nUptime: {health_after_8['uptime_seconds']:.0f}s")

print("\n" + "=" * 60)
print("Benchmark Complete")
print("=" * 60)