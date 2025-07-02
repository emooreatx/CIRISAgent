#!/usr/bin/env python3
"""Performance benchmark script for CIRIS API containers."""

import requests
import time
import statistics
from typing import List, Dict, Tuple
import json
from datetime import datetime
import concurrent.futures
import threading

class CIRISBenchmark:
    def __init__(self, base_url: str, username: str = "admin", password: str = "ciris_admin_password"):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.token = None
        self.channel_id = f"api_benchmark_{base_url.split(':')[-1]}"
        
    def login(self) -> bool:
        """Login and get authentication token."""
        try:
            response = requests.post(
                f"{self.base_url}/v1/auth/login",
                json={"username": self.username, "password": self.password}
            )
            if response.status_code == 200:
                self.token = response.json()["access_token"]
                print(f"✓ Logged in to {self.base_url}")
                return True
            else:
                print(f"✗ Login failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"✗ Login error: {e}")
            return False
    
    def send_command(self, command: str) -> Tuple[float, bool, str]:
        """Send a command and return (response_time, success, response_text)."""
        if not self.token:
            return 0.0, False, "Not authenticated"
            
        headers = {"Authorization": f"Bearer {self.token}"}
        start_time = time.time()
        
        try:
            response = requests.post(
                f"{self.base_url}/v1/agent/interact",
                headers=headers,
                json={"message": command, "channel_id": self.channel_id},
                timeout=30
            )
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                return response_time, True, response.json().get("response", "")
            else:
                return response_time, False, f"Error {response.status_code}: {response.text}"
                
        except requests.exceptions.Timeout:
            return time.time() - start_time, False, "Timeout"
        except Exception as e:
            return time.time() - start_time, False, f"Exception: {e}"
    
    def measure_handler_performance(self, handler: str, count: int = 10) -> Dict[str, float]:
        """Measure performance for a specific handler."""
        print(f"\n📊 Benchmarking {handler} handler ({count} requests)...")
        
        commands = {
            "SPEAK": "$speak Hello, this is a test message for benchmarking.",
            "RECALL": "$recall test",
            "MEMORIZE": "$memorize benchmark_test_{i} This is test memory item {i}"
        }
        
        response_times = []
        successes = 0
        
        for i in range(count):
            command = commands[handler]
            if "{i}" in command:
                command = command.format(i=i)
                
            response_time, success, response = self.send_command(command)
            
            if success:
                response_times.append(response_time)
                successes += 1
                print(f"  [{i+1}/{count}] ✓ {response_time:.3f}s")
            else:
                print(f"  [{i+1}/{count}] ✗ {response_time:.3f}s - {response}")
        
        if response_times:
            return {
                "handler": handler,
                "total_requests": count,
                "successful_requests": successes,
                "min_time": min(response_times),
                "max_time": max(response_times),
                "avg_time": statistics.mean(response_times),
                "median_time": statistics.median(response_times),
                "std_dev": statistics.stdev(response_times) if len(response_times) > 1 else 0
            }
        else:
            return {
                "handler": handler,
                "total_requests": count,
                "successful_requests": 0,
                "error": "All requests failed"
            }
    
    def throughput_test(self, command_count: int = 20) -> Dict[str, any]:
        """Test maximum throughput with rapid commands."""
        print(f"\n🚀 Throughput test ({command_count} rapid commands)...")
        
        start_time = time.time()
        results = []
        
        # Use thread pool for concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i in range(command_count):
                command = f"$speak Throughput test message {i}"
                future = executor.submit(self.send_command, command)
                futures.append(future)
            
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                response_time, success, response = future.result()
                results.append({
                    "index": i,
                    "response_time": response_time,
                    "success": success
                })
                
                status = "✓" if success else "✗"
                print(f"  [{i+1}/{command_count}] {status} {response_time:.3f}s")
        
        total_time = time.time() - start_time
        successful = sum(1 for r in results if r["success"])
        response_times = [r["response_time"] for r in results if r["success"]]
        
        return {
            "total_commands": command_count,
            "successful_commands": successful,
            "total_time": total_time,
            "throughput": successful / total_time if total_time > 0 else 0,
            "avg_response_time": statistics.mean(response_times) if response_times else 0,
            "min_response_time": min(response_times) if response_times else 0,
            "max_response_time": max(response_times) if response_times else 0
        }
    
    def get_system_health(self) -> Dict[str, any]:
        """Get system health and resource usage."""
        if not self.token:
            return {"error": "Not authenticated"}
            
        headers = {"Authorization": f"Bearer {self.token}"}
        
        try:
            response = requests.get(f"{self.base_url}/v1/system/health", headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Failed to get health: {response.status_code}"}
        except Exception as e:
            return {"error": f"Exception: {e}"}


def main():
    """Run benchmarks on containers 6 and 8."""
    
    print("=" * 80)
    print("CIRIS Performance Benchmark")
    print("=" * 80)
    
    # Container 6 benchmarks
    print("\n🔧 Container 6 (Port 8086) - Handler Performance Tests")
    print("-" * 60)
    
    benchmark6 = CIRISBenchmark("http://localhost:8086")
    if benchmark6.login():
        # Get initial health
        health_before = benchmark6.get_system_health()
        print(f"\nInitial health: {json.dumps(health_before, indent=2)}")
        
        # Benchmark each handler
        handlers = ["SPEAK", "RECALL", "MEMORIZE"]
        handler_results = []
        
        for handler in handlers:
            result = benchmark6.measure_handler_performance(handler, count=10)
            handler_results.append(result)
            time.sleep(1)  # Brief pause between handlers
        
        # Get final health
        health_after = benchmark6.get_system_health()
        
        # Print handler results
        print("\n📈 Handler Performance Summary:")
        print("-" * 60)
        for result in handler_results:
            if "error" not in result:
                print(f"\n{result['handler']}:")
                print(f"  Success Rate: {result['successful_requests']}/{result['total_requests']} ({result['successful_requests']/result['total_requests']*100:.1f}%)")
                print(f"  Avg Response: {result['avg_time']:.3f}s")
                print(f"  Min/Max: {result['min_time']:.3f}s / {result['max_time']:.3f}s")
                print(f"  Median: {result['median_time']:.3f}s")
                print(f"  Std Dev: {result['std_dev']:.3f}s")
            else:
                print(f"\n{result['handler']}: {result['error']}")
    
    # Container 8 throughput test
    print("\n\n🔧 Container 8 (Port 8088) - Throughput Test")
    print("-" * 60)
    
    benchmark8 = CIRISBenchmark("http://localhost:8088")
    if benchmark8.login():
        # Get initial health
        health_before = benchmark8.get_system_health()
        print(f"\nInitial health: Status={health_before.get('status', 'unknown')}, Uptime={health_before.get('uptime', 'unknown')}")
        
        # Run throughput test
        throughput_result = benchmark8.throughput_test(command_count=20)
        
        # Get final health
        health_after = benchmark8.get_system_health()
        
        # Print throughput results
        print("\n📈 Throughput Test Summary:")
        print("-" * 60)
        print(f"Total Commands: {throughput_result['total_commands']}")
        print(f"Successful: {throughput_result['successful_commands']} ({throughput_result['successful_commands']/throughput_result['total_commands']*100:.1f}%)")
        print(f"Total Time: {throughput_result['total_time']:.2f}s")
        print(f"Throughput: {throughput_result['throughput']:.2f} commands/second")
        print(f"Avg Response Time: {throughput_result['avg_response_time']:.3f}s")
        print(f"Min/Max Response: {throughput_result['min_response_time']:.3f}s / {throughput_result['max_response_time']:.3f}s")
        
        # Check for resource changes
        if isinstance(health_before, dict) and isinstance(health_after, dict):
            if "memory_usage" in health_before and "memory_usage" in health_after:
                memory_before = health_before["memory_usage"]["percent"]
                memory_after = health_after["memory_usage"]["percent"]
                print(f"\nMemory Usage: {memory_before:.1f}% → {memory_after:.1f}% (Δ{memory_after-memory_before:+.1f}%)")
    
    print("\n" + "=" * 80)
    print("Benchmark Complete")
    print("=" * 80)


if __name__ == "__main__":
    main()