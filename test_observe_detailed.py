#!/usr/bin/env python3
"""Test API observation handler on a specific container."""

import requests
import json
import time
import sys

def test_observe_handler(port=8084):
    """Test the OBSERVE handler on a container."""
    base_url = f"http://localhost:{port}"
    
    print(f"\n=== Testing OBSERVE Handler on Container (port {port}) ===\n")
    
    # Step 1: Login
    print("1. Logging in...")
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
    print(f"✅ Login successful - Token: {token[:20]}...")
    
    # Step 2: Send OBSERVE command
    channel_id = f"api_0.0.0.0_{port}"  # Use the format that API uses
    observe_message = f"$observe {channel_id}"
    
    print(f"\n2. Sending OBSERVE command: '{observe_message}'")
    print(f"   Channel ID: {channel_id}")
    
    observe_response = requests.post(
        f"{base_url}/v1/agent/interact",
        headers=headers,
        json={
            "message": observe_message,
            "channel_id": channel_id
        }
    )
    
    print(f"\n3. Response Status: {observe_response.status_code}")
    
    if observe_response.status_code == 200:
        response_data = observe_response.json()
        print(f"\n4. Response Data:")
        print(json.dumps(response_data, indent=2))
        
        # Check if it's a timeout response
        if "processing_time_ms" in response_data.get("data", {}):
            processing_time = response_data["data"]["processing_time_ms"]
            if processing_time >= 30000:
                print(f"\n⚠️  Response timed out after {processing_time/1000} seconds")
                print("This might indicate the OBSERVE handler isn't processing correctly")
        
        # Check the actual response content
        if "response" in response_data.get("data", {}):
            response_text = response_data["data"]["response"]
            print(f"\n5. Agent Response: {response_text}")
            
            # Check if it's a mock LLM response
            if "[MOCK LLM]" in response_text:
                print("✅ Mock LLM processed the command")
            elif "still processing" in response_text.lower():
                print("⚠️  Agent is still processing - timeout occurred")
            else:
                print("❓ Unexpected response format")
    else:
        print(f"❌ Observe request failed: {observe_response.status_code}")
        print(f"Response: {observe_response.text}")
        return False
    
    # Step 3: Wait a bit and check if observation was created
    print("\n6. Waiting 2 seconds for observation to be processed...")
    time.sleep(2)
    
    # Step 4: Send a follow-up message to see if observation worked
    print("\n7. Sending follow-up message to check observation...")
    followup_response = requests.post(
        f"{base_url}/v1/agent/interact",
        headers=headers,
        json={
            "message": "$speak Observation test complete",
            "channel_id": channel_id
        }
    )
    
    if followup_response.status_code == 200:
        followup_data = followup_response.json()
        print("\n8. Follow-up Response:")
        print(json.dumps(followup_data, indent=2))
    
    return True

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8084
    success = test_observe_handler(port)
    print(f"\n{'✅ Test completed' if success else '❌ Test failed'}")