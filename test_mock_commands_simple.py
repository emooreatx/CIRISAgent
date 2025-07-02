#!/usr/bin/env python3
"""Simple test to verify mock LLM command handling"""

import requests
import json
import time

def test_command(port, command, description):
    """Test a single command"""
    print(f"\n{'='*50}")
    print(f"Testing: {description}")
    print(f"Command: {command}")
    print(f"{'='*50}")
    
    # Login
    login_response = requests.post(
        f"http://localhost:{port}/v1/auth/login",
        json={"username": "admin", "password": "ciris_admin_password"}
    )
    
    if login_response.status_code != 200:
        print(f"Login failed: {login_response.text}")
        return
    
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Send command
    channel_id = f"api_test_{port}"
    request_data = {
        "message": command,
        "channel_id": channel_id
    }
    
    print(f"Sending: {json.dumps(request_data)}")
    
    response = requests.post(
        f"http://localhost:{port}/v1/agent/interact",
        headers=headers,
        json=request_data
    )
    
    if response.status_code == 200:
        data = response.json()
        if "data" in data and "response" in data["data"]:
            response_text = data["data"]["response"]
            print(f"Response: {response_text}")
            
            # Analyze response
            if command.startswith("$speak") and "SPEAK" in response_text:
                print("✓ SPEAK handler detected")
            elif command.startswith("$recall") and "RECALL" in response_text:
                print("✓ RECALL handler detected")
            elif command.startswith("$memorize") and "MEMORIZE" in response_text:
                print("✓ MEMORIZE handler detected")
            elif command.startswith("$help") and "Commands Help" in response_text:
                print("✓ HELP response detected")
            elif "MOCKLLM DISCLAIMER" in response_text:
                print("⚠ Generic SPEAK response (not command-specific)")
            else:
                print("? Unknown response type")
    else:
        print(f"Request failed: {response.status_code}")
        print(response.text)

def main():
    # Test help first to see if commands work at all
    test_command(8080, "$help", "Help command on container 0")
    
    # Test specific commands
    test_command(8080, "$speak Hello world", "SPEAK command on container 0")
    test_command(8081, "$recall memories", "RECALL command on container 1")
    test_command(8080, "$memorize test_memory", "MEMORIZE command on container 0")
    
    # Test regular messages
    test_command(8080, "Hello, what is your purpose?", "Regular message on container 0")

if __name__ == "__main__":
    main()