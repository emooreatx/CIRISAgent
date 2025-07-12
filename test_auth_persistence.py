#!/usr/bin/env python3
"""Test API authentication persistence."""

import asyncio
import httpx
import json

async def test_auth_persistence():
    base_url = "http://localhost:8080/v1"
    
    # First, login as admin
    print("1. Logging in as admin...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url}/auth/login",
            json={"username": "admin", "password": "ciris_admin_password"}
        )
        if response.status_code != 200:
            print(f"Login failed: {response.text}")
            return
        
        admin_token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {admin_token}"}
        print(f"   Got admin token: {admin_token[:20]}...")
        
        # Try to create a new user (or check if it exists)
        print("\n2. Creating/checking user 'testuser'...")
        response = await client.post(
            f"{base_url}/users",
            headers=headers,
            json={
                "username": "testuser",
                "password": "testpass123",
                "role": "observer"
            }
        )
        if response.status_code in [200, 201]:
            user_data = response.json()
            print(f"   Created user: {json.dumps(user_data, indent=2)}")
            test_user_id = user_data.get("user_id") or user_data.get("wa_id")
        elif "already exists" in response.text:
            print(f"   User already exists (good - persistence working!)")
        else:
            print(f"   Unexpected error: {response.text}")
            return
        
        # List all users
        print("\n3. Listing all users...")
        response = await client.get(
            f"{base_url}/users",
            headers=headers
        )
        if response.status_code == 200:
            data = response.json()
            users = data.get("items", [])  # Paginated response
            print(f"   Found {len(users)} users:")
            for user in users:
                print(f"     - {user.get('username', user.get('name', 'N/A'))} ({user.get('user_id', user.get('wa_id', 'N/A'))}) - Role: {user.get('api_role', 'N/A')}")
        
        # Test login with new user
        print("\n4. Testing login with new user...")
        response = await client.post(
            f"{base_url}/auth/login",
            json={"username": "testuser", "password": "testpass123"}
        )
        if response.status_code == 200:
            test_token = response.json()["access_token"]
            print(f"   Login successful! Token: {test_token[:20]}...")
        else:
            print(f"   Login failed: {response.text}")
        
        # Get WA status
        print("\n5. Checking WA certificates...")
        response = await client.get(
            f"{base_url}/wa/certificates",
            headers=headers
        )
        if response.status_code == 200:
            certs = response.json()
            print(f"   Found {len(certs)} WA certificates:")
            for cert in certs:
                print(f"     - {cert['name']} ({cert['wa_id']}) - Role: {cert.get('role', 'N/A')}")
        
        print("\n6. IMPORTANT: Now restart the container to test persistence!")
        print("   Run: docker restart container0")
        print("   Then run this script again to verify users are still there.")

if __name__ == "__main__":
    asyncio.run(test_auth_persistence())