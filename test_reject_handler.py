#!/usr/bin/env python3
"""Test REJECT handler on container7 (port 8087)"""

import requests
import json
import sys
from datetime import datetime

def test_reject_handler():
    """Test the REJECT handler on container7"""
    base_url = "http://localhost:8087"
    
    print(f"\n=== Testing REJECT handler on container7 (port 8087) ===")
    print(f"Time: {datetime.now().isoformat()}")
    
    # Step 1: Login
    print("\n1. Logging in with admin/ciris_admin_password...")
    login_response = requests.post(
        f"{base_url}/v1/auth/login",
        json={"username": "admin", "password": "ciris_admin_password"}
    )
    
    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.status_code}")
        print(f"Response: {login_response.text}")
        return False
    
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"✅ Login successful, got token")
    
    # Step 2: Send reject command
    print("\n2. Sending: '$reject Inappropriate request'...")
    interact_response = requests.post(
        f"{base_url}/v1/agent/interact",
        headers=headers,
        json={
            "message": "$reject Inappropriate request",
            "channel_id": "api_test_reject"
        }
    )
    
    if interact_response.status_code != 200:
        print(f"❌ Interact failed: {interact_response.status_code}")
        print(f"Response: {interact_response.text}")
        return False
    
    # Step 3: Verify rejection response
    print("\n3. Verifying rejection response...")
    response_data = interact_response.json()
    print(f"Response: {json.dumps(response_data, indent=2)}")
    
    # Check if response indicates rejection
    if "response" in response_data:
        response_text = response_data["response"].lower()
        if any(word in response_text for word in ["reject", "inappropriate", "cannot", "won't", "refuse"]):
            print("✅ Response indicates rejection")
        else:
            print("⚠️  Response doesn't clearly indicate rejection")
    
    # Step 4: Check container health
    print("\n4. Checking container health...")
    health_response = requests.get(
        f"{base_url}/v1/system/health",
        headers={"Authorization": "Bearer admin:ciris_admin_password"}
    )
    
    if health_response.status_code == 200:
        health_data = health_response.json()
        print(f"✅ Container is healthy")
        print(f"   Uptime: {health_data.get('uptime', 'Unknown')}")
        print(f"   Services: {health_data.get('services', {}).get('total', 0)} total, {health_data.get('services', {}).get('healthy', 0)} healthy")
    else:
        print(f"❌ Health check failed: {health_response.status_code}")
    
    return True

if __name__ == "__main__":
    try:
        success = test_reject_handler()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)