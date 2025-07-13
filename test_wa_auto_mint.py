#!/usr/bin/env python3
"""Test WA auto-minting with server-side signing."""

import asyncio
import httpx
import json
import os
from pathlib import Path

async def test_wa_auto_mint():
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
        
        # Check if private key exists
        key_path = "~/.ciris/wa_keys/root_wa.key"
        print(f"\n2. Checking if private key exists at {key_path}...")
        response = await client.get(
            f"{base_url}/users/wa/key-check",
            headers=headers,
            params={"path": key_path}
        )
        if response.status_code == 200:
            key_info = response.json()
            print(f"   Key check result: {json.dumps(key_info, indent=2)}")
            
            if not key_info.get("exists"):
                print("\n   ERROR: Private key not found. Please generate it first:")
                print("   python /home/emoore/CIRISAgent/generate_root_wa_keypair.py")
                return
        else:
            print(f"   Failed to check key: {response.text}")
            return
        
        # Get or create test user
        print("\n3. Getting test user for minting...")
        response = await client.get(
            f"{base_url}/users",
            headers=headers,
            params={"search": "testuser"}
        )
        
        test_user = None
        if response.status_code == 200:
            users = response.json().get("items", [])
            for user in users:
                if user.get("username") == "testuser":
                    test_user = user
                    break
        
        if not test_user:
            print("   Creating testuser...")
            response = await client.post(
                f"{base_url}/users",
                headers=headers,
                json={
                    "username": "testuser",
                    "password": "testpass123",
                    "api_role": "observer"
                }
            )
            if response.status_code in [200, 201]:
                test_user = response.json()
            else:
                print(f"   Failed to create user: {response.text}")
                return
        
        print(f"   Test user ID: {test_user['user_id']}")
        print(f"   Current WA role: {test_user.get('wa_role', 'None')}")
        
        # Test auto-minting
        print("\n4. Testing auto-mint with server-side signing...")
        response = await client.post(
            f"{base_url}/users/{test_user['user_id']}/mint-wa",
            headers=headers,
            json={
                "wa_role": "observer",
                "private_key_path": key_path
                # Note: no signature provided!
            }
        )
        
        if response.status_code == 200:
            minted_user = response.json()
            print("   SUCCESS! User minted as WA:")
            print(f"   - WA role: {minted_user.get('wa_role')}")
            print(f"   - WA ID: {minted_user.get('wa_id')}")
            print(f"   - Minted by: {minted_user.get('wa_parent_id', 'N/A')}")
        else:
            print(f"   Failed to mint: {response.text}")
            
            # Try with manual signature for comparison
            print("\n5. Trying with manual signature...")
            import asyncio
            proc = await asyncio.create_subprocess_exec(
                "python", "/home/emoore/CIRISAgent/sign_wa_mint.py", 
                test_user['user_id'], "observer",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if stdout:
                print(stdout.decode())
            if stderr:
                print(f"Error: {stderr.decode()}")

if __name__ == "__main__":
    asyncio.run(test_wa_auto_mint())