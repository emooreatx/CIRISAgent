#!/usr/bin/env python3
"""Test DEFER and REJECT handlers on containers 6 and 7"""

import requests
import json
import time
from datetime import datetime

def test_handler(container_num, port, handler_type, test_cases):
    """Test a specific handler on a container"""
    print(f"\n{'='*60}")
    print(f"Testing {handler_type} handler on Container {container_num} (port {port})")
    print(f"{'='*60}")
    
    # Login first
    login_url = f"http://localhost:{port}/v1/auth/login"
    login_data = {"username": "admin", "password": "ciris_admin_password"}
    
    print(f"\n1. Logging in to container {container_num}...")
    try:
        response = requests.post(login_url, json=login_data)
        if response.status_code == 200:
            token = response.json()["access_token"]
            print(f"   ✓ Login successful - Token received")
        else:
            print(f"   ✗ Login failed: {response.status_code} - {response.text}")
            return
    except Exception as e:
        print(f"   ✗ Login error: {e}")
        return
    
    # Test each case
    headers = {"Authorization": f"Bearer {token}"}
    interact_url = f"http://localhost:{port}/v1/agent/interact"
    
    for i, (desc, message) in enumerate(test_cases, 1):
        print(f"\n{i+1}. Testing: {desc}")
        print(f"   Command: {message}")
        
        try:
            start_time = time.time()
            response = requests.post(
                interact_url,
                headers=headers,
                json={"message": message, "channel_id": f"api_test_{port}"}
            )
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✓ Response received (Status: 200)")
                print(f"   Response time: {response_time:.2f}ms")
                print(f"   Handler triggered: {handler_type in str(data).upper()}")
                print(f"   Response content:")
                print(f"   {json.dumps(data, indent=4)}")
                
                # Check if handler was properly triggered
                if "status" in data and data["status"].upper() == handler_type:
                    print(f"   ✓ {handler_type} handler correctly triggered!")
                elif "response" in data and handler_type in data["response"].upper():
                    print(f"   ✓ {handler_type} response detected in message!")
                else:
                    print(f"   ⚠ {handler_type} handler may not have been triggered properly")
                    
            else:
                print(f"   ✗ Error: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"   ✗ Request error: {e}")

def main():
    """Run all handler tests"""
    print("DEFER and REJECT Handler Tests")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test DEFER handler on container 6
    defer_tests = [
        ("Basic defer command", "$defer I need more information before I can answer"),
        ("Defer with reason", "$defer Waiting for admin approval"),
        ("Complex defer", "$defer Cannot process request: missing required context about user preferences")
    ]
    test_handler(6, 8086, "DEFER", defer_tests)
    
    # Test REJECT handler on container 7
    reject_tests = [
        ("Basic reject command", "$reject This request violates ethical guidelines"),
        ("Reject with reason", "$reject Cannot process harmful content"),
        ("Complex reject", "$reject Request denied: attempting to access restricted functionality")
    ]
    test_handler(7, 8087, "REJECT", reject_tests)
    
    print(f"\n\nTests completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()