#!/usr/bin/env python3
"""Test correlation-based message fetching for API adapter."""

import asyncio
import httpx
import json
from datetime import datetime

# API configuration
API_URL = "http://localhost:8080"
USERNAME = "admin"
PASSWORD = "ciris_admin_password"

async def main():
    async with httpx.AsyncClient() as client:
        # 1. Login to get auth token
        print("1. Logging in...")
        login_response = await client.post(
            f"{API_URL}/v1/auth/login",
            json={"username": USERNAME, "password": PASSWORD}
        )
        if login_response.status_code != 200:
            print(f"Login failed: {login_response.text}")
            return
        
        auth_data = login_response.json()
        print(f"Auth response: {auth_data}")
        
        # Check for different possible token field names
        token = auth_data.get("token") or auth_data.get("access_token") or auth_data.get("api_key")
        if not token:
            print(f"No token found in response: {auth_data}")
            return
            
        headers = {"Authorization": f"Bearer {token}"}
        print(f"✓ Logged in successfully")
        
        # 2. Get default channel from system health
        print("\n2. Getting system health...")
        system_response = await client.get(
            f"{API_URL}/v1/system/health",
            headers=headers
        )
        
        if system_response.status_code != 200:
            print(f"System health failed: {system_response.text}")
            # Use default channel
            default_channel = "api_0.0.0.0_8080"
        else:
            # For now, we know the default channel format
            default_channel = "api_0.0.0.0_8080"
        print(f"✓ Default channel: {default_channel}")
        
        # 3. Check messages in the default channel (should show WAKEUP messages)
        print(f"\n3. Checking messages in channel {default_channel}...")
        interaction_response = await client.post(
            f"{API_URL}/v1/agent/interact",
            headers=headers,
            json={
                "prompt": "",  # Empty prompt to just fetch messages
                "channel": default_channel,
                "mode": "async"
            }
        )
        
        if interaction_response.status_code == 200:
            interaction_data = interaction_response.json()
            print(f"✓ Found {len(interaction_data.get('history', []))} messages in history")
            
            # Display message history
            for msg in interaction_data.get('history', []):
                timestamp = msg.get('timestamp', 'unknown')
                author = msg.get('author_name', 'unknown')
                content = msg.get('content', '')[:100]  # First 100 chars
                is_agent = msg.get('is_agent_message', False)
                print(f"  [{timestamp}] {author} {'(CIRIS)' if is_agent else '(User)'}: {content}...")
        
        # 4. Send a test message
        print("\n4. Sending test message...")
        test_response = await client.post(
            f"{API_URL}/v1/agent/interact",
            headers=headers,
            json={
                "prompt": "What is 2+2?",
                "channel": default_channel
            }
        )
        
        if test_response.status_code == 200:
            response_data = test_response.json()
            print(f"✓ Response: {response_data.get('response', 'No response')}")
            
            # Wait a moment for correlation to be saved
            await asyncio.sleep(1)
            
            # 5. Check messages again to see our interaction
            print("\n5. Checking messages again...")
            final_check = await client.post(
                f"{API_URL}/v1/agent/interact",
                headers=headers,
                json={
                    "prompt": "",
                    "channel": default_channel,
                    "mode": "async"
                }
            )
            
            if final_check.status_code == 200:
                final_data = final_check.json()
                new_count = len(final_data.get('history', []))
                print(f"✓ Now found {new_count} messages in history")
                
                # Show last few messages
                print("\nLast 3 messages:")
                for msg in final_data.get('history', [])[-3:]:
                    timestamp = msg.get('timestamp', 'unknown')
                    author = msg.get('author_name', 'unknown')
                    content = msg.get('content', '')[:100]
                    is_agent = msg.get('is_agent_message', False)
                    print(f"  [{timestamp}] {author} {'(CIRIS)' if is_agent else '(User)'}: {content}...")

if __name__ == "__main__":
    asyncio.run(main())