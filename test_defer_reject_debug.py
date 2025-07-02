#!/usr/bin/env python3
"""Debug test for DEFER and REJECT handlers"""

import requests
import json
import time

def test_single_command(port, command):
    """Test a single command and show full response"""
    print(f"\n{'='*60}")
    print(f"Testing on port {port}: {command}")
    print(f"{'='*60}")
    
    # Login
    login_url = f"http://localhost:{port}/v1/auth/login"
    login_data = {"username": "admin", "password": "ciris_admin_password"}
    
    try:
        response = requests.post(login_url, json=login_data)
        if response.status_code == 200:
            token = response.json()["access_token"]
            print(f"✓ Login successful")
        else:
            print(f"✗ Login failed: {response.status_code}")
            return
    except Exception as e:
        print(f"✗ Login error: {e}")
        return
    
    # Send command
    headers = {"Authorization": f"Bearer {token}"}
    interact_url = f"http://localhost:{port}/v1/agent/interact"
    
    # Use the actual channel_id format that the API creates
    request_data = {
        "message": command,
        "channel_id": f"api_ADMIN"  # This will be overridden to api_admin by the API
    }
    
    print(f"\nRequest:")
    print(json.dumps(request_data, indent=2))
    
    try:
        start_time = time.time()
        response = requests.post(interact_url, headers=headers, json=request_data)
        response_time = (time.time() - start_time) * 1000
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Time: {response_time:.2f}ms")
        print(f"\nResponse Body:")
        print(json.dumps(response.json(), indent=2))
        
    except Exception as e:
        print(f"\n✗ Request error: {e}")

def main():
    """Run focused debug tests"""
    
    # Test basic defer
    print("\n" + "="*80)
    print("DEFER HANDLER DEBUG TEST")
    print("="*80)
    test_single_command(8086, "$defer I need more information")
    
    # Test basic reject  
    print("\n" + "="*80)
    print("REJECT HANDLER DEBUG TEST")
    print("="*80)
    test_single_command(8087, "$reject This violates guidelines")
    
    # Test with forced_action context
    print("\n" + "="*80)
    print("TESTING FORCED ACTION CONTEXT")
    print("="*80)
    
    # Try sending context in the message itself
    test_single_command(8086, "forced_action:defer action_params:Testing defer handler")
    test_single_command(8087, "forced_action:reject action_params:Testing reject handler")

if __name__ == "__main__":
    main()