#!/usr/bin/env python3
"""Test SPEAK and RECALL handlers with debugging"""

import requests
import json
import time
from datetime import datetime

def test_single_command(port, command, description):
    """Test a single command and return detailed results"""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"Port: {port}, Command: {command}")
    print(f"{'='*60}")
    
    # Login
    login_url = f"http://localhost:{port}/v1/auth/login"
    login_data = {"username": "admin", "password": "ciris_admin_password"}
    
    try:
        login_response = requests.post(login_url, json=login_data)
        if login_response.status_code != 200:
            print(f"✗ Login failed: {login_response.status_code}")
            return None
            
        token = login_response.json()["access_token"]
        print(f"✓ Login successful")
    except Exception as e:
        print(f"✗ Login error: {str(e)}")
        return None
    
    # Send command
    headers = {"Authorization": f"Bearer {token}"}
    interact_url = f"http://localhost:{port}/v1/agent/interact"
    
    # Try different channel ID formats
    channel_ids = [
        f"api_test_{port}",
        f"api_0.0.0.0_{port}",
        f"api_SYSTEM_ADMIN"
    ]
    
    for channel_id in channel_ids:
        print(f"\nTrying channel_id: {channel_id}")
        
        request_data = {
            "message": command,
            "channel_id": channel_id
        }
        
        print(f"Request data: {json.dumps(request_data, indent=2)}")
        
        try:
            start_time = time.time()
            response = requests.post(interact_url, headers=headers, json=request_data)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Request successful (took {response_time:.3f}s)")
                
                # Extract response from nested structure
                if "data" in data and "response" in data["data"]:
                    response_text = data["data"]["response"]
                    print(f"Response: {response_text}")
                    
                    # Check if this is the expected response type
                    if "$speak" in command and "SPEAK" in response_text:
                        print("✓ SPEAK handler triggered correctly")
                        return True
                    elif "$recall" in command and ("RECALL" in response_text or "memories" in response_text):
                        print("✓ RECALL handler triggered correctly")  
                        return True
                    else:
                        print(f"⚠️  Unexpected response for command: {command}")
                        
                print(f"\nFull response:")
                print(json.dumps(data, indent=2))
                
                # Only try first channel that works
                break
            else:
                print(f"✗ Request failed: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"✗ Request error: {str(e)}")
    
    return False

def main():
    """Main test function"""
    print(f"Starting handler tests at {datetime.now()}")
    
    # Test individual commands
    tests = [
        # Container 0 - SPEAK tests
        (8080, "$speak Hello from SPEAK test", "Direct $speak command on container 0"),
        (8080, "$speak", "Empty $speak command (should show help)"),
        (8080, "What is your purpose?", "Regular message (should trigger SPEAK)"),
        
        # Container 1 - RECALL tests  
        (8081, "$recall memories", "Direct $recall command on container 1"),
        (8081, "$recall test memories", "$recall with specific query"),
        (8081, "$recall", "Empty $recall command (should show help)"),
    ]
    
    results = []
    for port, command, description in tests:
        result = test_single_command(port, command, description)
        results.append((description, result))
        time.sleep(1)  # Brief pause between tests
    
    # Summary
    print(f"\n\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    for description, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {description}")
    
    print(f"\nTests completed at {datetime.now()}")

if __name__ == "__main__":
    main()