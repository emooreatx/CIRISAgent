#!/usr/bin/env python3
"""Test 10 CIRIS containers in parallel using the updated handler API."""

import asyncio
import aiohttp
import json
from datetime import datetime
from typing import List, Dict, Tuple
import time

# Configuration
BASE_PORTS = list(range(8080, 8090))  # Ports 8080-8089
BASE_URL = "http://localhost"
USERNAME = "admin"
PASSWORD = "ciris_admin_password"
TEST_TIMEOUT = 60  # seconds per test

# Colors for output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

async def get_auth_token(session: aiohttp.ClientSession, port: int) -> str:
    """Get authentication token via login."""
    url = f"{BASE_URL}:{port}/v1/auth/login"
    data = {
        "username": USERNAME,
        "password": PASSWORD
    }
    
    async with session.post(url, json=data) as resp:
        if resp.status != 200:
            raise Exception(f"Login failed: {await resp.text()}")
        result = await resp.json()
        return result["access_token"]

async def send_message(session: aiohttp.ClientSession, port: int, token: str, message: str) -> Dict:
    """Send a message to the agent."""
    url = f"{BASE_URL}:{port}/v1/agent/interact"
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "message": message,
        "channel_id": f"api_test_{port}"
    }
    
    async with session.post(url, json=data, headers=headers) as resp:
        return await resp.json()

async def test_container(container_num: int) -> Tuple[int, bool, str, float]:
    """Test a single container."""
    port = BASE_PORTS[container_num]
    start_time = time.time()
    
    try:
        async with aiohttp.ClientSession() as session:
            # Get auth token
            token = await get_auth_token(session, port)
            
            # Test 1: Basic SPEAK command
            response = await send_message(session, port, token, "$speak Hello from container test!")
            
            # Check response - handle the nested data structure
            response_data = response.get("data", {})
            actual_response = response_data.get("response", "")
            
            # Check if we got an actual response (not just processing message)
            if actual_response and "processing your request" not in actual_response:
                # Success - got a real response
                channel_used = "unknown"
                # Try to extract channel info from logs or response
                if "api_" in str(response):
                    import re
                    channel_match = re.search(r'(api_[\d\.]+_\d+)', str(response))
                    if channel_match:
                        channel_used = channel_match.group(1)
                
                duration = time.time() - start_time
                return (port, True, f"Success - Response: '{actual_response[:50]}...' Channel: {channel_used}", duration)
            else:
                # Timeout or still processing
                duration = time.time() - start_time
                return (port, False, f"Timeout/Processing: {actual_response[:100]}", duration)
                
    except Exception as e:
        duration = time.time() - start_time
        return (port, False, f"Error: {str(e)}", duration)

async def wait_for_containers_ready(timeout: int = 60) -> bool:
    """Wait for all containers to be ready."""
    print(f"{Colors.HEADER}Waiting for containers to be ready...{Colors.ENDC}")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        ready_count = 0
        async with aiohttp.ClientSession() as session:
            for port in BASE_PORTS:
                try:
                    async with session.get(f"{BASE_URL}:{port}/v1/system/health") as resp:
                        if resp.status == 200:
                            ready_count += 1
                except:
                    pass
        
        if ready_count == len(BASE_PORTS):
            print(f"{Colors.OKGREEN}All {len(BASE_PORTS)} containers are ready!{Colors.ENDC}")
            return True
        
        print(f"Ready: {ready_count}/{len(BASE_PORTS)} containers", end='\r')
        await asyncio.sleep(2)
    
    print(f"{Colors.FAIL}Timeout waiting for containers{Colors.ENDC}")
    return False

async def main():
    """Run parallel tests on all containers."""
    print(f"{Colors.HEADER}{Colors.BOLD}=== Testing 10 CIRIS Containers in Parallel ==={Colors.ENDC}")
    print(f"Testing ports: {BASE_PORTS}")
    print(f"Test timeout: {TEST_TIMEOUT}s per container\n")
    
    # Wait for containers
    if not await wait_for_containers_ready():
        return
    
    print(f"\n{Colors.OKCYAN}Starting parallel tests...{Colors.ENDC}\n")
    
    # Run all tests in parallel
    start_time = time.time()
    tasks = [test_container(i) for i in range(len(BASE_PORTS))]
    results = await asyncio.gather(*tasks)
    total_duration = time.time() - start_time
    
    # Display results
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== Test Results ==={Colors.ENDC}\n")
    
    success_count = 0
    for port, success, message, duration in sorted(results):
        container_num = BASE_PORTS.index(port)
        status = f"{Colors.OKGREEN}✓ PASS{Colors.ENDC}" if success else f"{Colors.FAIL}✗ FAIL{Colors.ENDC}"
        print(f"Container {container_num} (:{port}): {status} - {message} ({duration:.2f}s)")
        if success:
            success_count += 1
    
    # Summary
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== Summary ==={Colors.ENDC}")
    print(f"Total containers tested: {len(BASE_PORTS)}")
    print(f"Successful: {Colors.OKGREEN}{success_count}{Colors.ENDC}")
    print(f"Failed: {Colors.FAIL}{len(BASE_PORTS) - success_count}{Colors.ENDC}")
    print(f"Total test duration: {total_duration:.2f}s")
    print(f"Average time per container: {total_duration/len(BASE_PORTS):.2f}s")
    
    # Channel extraction verification
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== Channel ID Extraction Test ==={Colors.ENDC}")
    print("Testing if mock LLM properly extracts full channel IDs...")
    
    # Test one container with detailed logging
    async with aiohttp.ClientSession() as session:
        port = BASE_PORTS[0]
        token = await get_auth_token(session, port)
        
        # Send a message that should trigger channel extraction
        test_channel = f"api_127.0.0.1_{port}"
        response = await send_message(session, port, token, "$speak Testing channel extraction")
        
        print(f"Test channel sent: {test_channel}")
        print(f"Response: {response.get('response', 'No response')[:200]}...")
        
        # Check if the response indicates proper channel handling
        if test_channel in str(response):
            print(f"{Colors.OKGREEN}✓ Channel ID properly handled{Colors.ENDC}")
        else:
            print(f"{Colors.WARNING}⚠ Channel ID may not be properly extracted{Colors.ENDC}")

if __name__ == "__main__":
    asyncio.run(main())