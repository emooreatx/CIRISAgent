#!/usr/bin/env python3
"""Simple test for API interaction."""

import asyncio
import httpx
import json

API_URL = "http://localhost:8080"
USERNAME = "admin"
PASSWORD = "ciris_admin_password"

async def main():
    async with httpx.AsyncClient() as client:
        # 1. Login
        print("1. Logging in...")
        login_response = await client.post(
            f"{API_URL}/v1/auth/login",
            json={"username": USERNAME, "password": PASSWORD}
        )
        
        if login_response.status_code != 200:
            print(f"Login failed: {login_response.text}")
            return
            
        auth_data = login_response.json()
        token = auth_data.get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        print("✓ Logged in successfully")
        
        # 2. Send a simple message
        print("\n2. Sending test message...")
        interact_response = await client.post(
            f"{API_URL}/v1/agent/interact",
            headers=headers,
            json={
                "message": "What is 2+2?"
            }
        )
        
        print(f"Status: {interact_response.status_code}")
        if interact_response.status_code == 200:
            data = interact_response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
        else:
            print(f"Error: {interact_response.text}")

if __name__ == "__main__":
    asyncio.run(main())