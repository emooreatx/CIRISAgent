#!/usr/bin/env python3
"""Test SPEAK and RECALL handlers on containers 0 and 1"""

import requests
import json
import time
from datetime import datetime

def test_container(port, container_name, tests):
    """Test a specific handler on a container"""
    print(f"\n{'='*60}")
    print(f"Testing {container_name} on port {port}")
    print(f"{'='*60}")
    
    # Login
    login_url = f"http://localhost:{port}/v1/auth/login"
    login_data = {"username": "admin", "password": "ciris_admin_password"}
    
    print(f"\n1. Logging in to {login_url}")
    try:
        login_start = time.time()
        login_response = requests.post(login_url, json=login_data)
        login_time = time.time() - login_start
        
        if login_response.status_code == 200:
            token = login_response.json()["access_token"]
            print(f"✓ Login successful (took {login_time:.3f}s)")
            print(f"  Token: {token[:50]}...")
        else:
            print(f"✗ Login failed: {login_response.status_code}")
            print(f"  Response: {login_response.text}")
            return
    except Exception as e:
        print(f"✗ Login error: {str(e)}")
        return
    
    # Prepare headers
    headers = {"Authorization": f"Bearer {token}"}
    interact_url = f"http://localhost:{port}/v1/agent/interact"
    
    # Run tests
    for i, (test_name, message) in enumerate(tests, 2):
        print(f"\n{i}. Testing: {test_name}")
        print(f"   Message: {message}")
        
        try:
            start_time = time.time()
            response = requests.post(
                interact_url,
                headers=headers,
                json={"message": message, "channel_id": f"api_test_{port}"}
            )
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Request successful (took {response_time:.3f}s)")
                print(f"  Response content: {data.get('response', 'No response field')}")
                
                # Check if it's a streaming response
                if "stream_url" in data:
                    print(f"  Stream URL provided: {data['stream_url']}")
                    
                # Print full response for debugging
                print(f"  Full response data:")
                print(json.dumps(data, indent=2))
            else:
                print(f"✗ Request failed: {response.status_code}")
                print(f"  Response: {response.text}")
                
        except Exception as e:
            print(f"✗ Request error: {str(e)}")

def main():
    """Main test function"""
    print(f"Starting handler tests at {datetime.now()}")
    
    # Test SPEAK handler on container 0
    speak_tests = [
        ("Direct $speak command", "$speak Hello from SPEAK test on container 0"),
        ("Regular message triggering SPEAK", "What is your purpose?"),
        ("Another SPEAK trigger", "Tell me about yourself")
    ]
    test_container(8080, "Container 0 - SPEAK Handler", speak_tests)
    
    # Test RECALL handler on container 1
    recall_tests = [
        ("Direct $recall command", "$recall memories"),
        ("$recall with specific query", "$recall test memories"),
        ("$recall recent interactions", "$recall recent interactions")
    ]
    test_container(8081, "Container 1 - RECALL Handler", recall_tests)
    
    print(f"\n\nTests completed at {datetime.now()}")

if __name__ == "__main__":
    main()