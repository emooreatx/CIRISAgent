#!/usr/bin/env python3
"""
Test granting permissions to users.
"""
import requests
import json

BASE_URL = "http://localhost:8080"

# Step 1: Admin login
print("1. Admin login...")
admin_resp = requests.post(
    f"{BASE_URL}/v1/auth/login",
    json={"username": "admin", "password": "ciris_admin_password"}
)
admin_token = admin_resp.json()["access_token"]
admin_role = admin_resp.json()["role"]
print(f"   Admin token: {admin_token[:20]}...")
print(f"   Admin role: {admin_role}")

# Step 2: Check admin permissions
print("\n2. Checking admin permissions...")
me_resp = requests.get(
    f"{BASE_URL}/v1/auth/me",
    headers={"Authorization": f"Bearer {admin_token}"}
)
admin_info = me_resp.json()
print(f"   User ID: {admin_info['user_id']}")
print(f"   Role: {admin_info['role']}")
print(f"   Permissions: {json.dumps(admin_info['permissions'], indent=2)}")

has_manage_perms = "manage_user_permissions" in admin_info['permissions']
print(f"\n   Has manage_user_permissions: {has_manage_perms}")

# Step 3: Get permission requests
print("\n3. Getting permission requests...")
perm_requests = requests.get(
    f"{BASE_URL}/v1/users/permission-requests",
    headers={"Authorization": f"Bearer {admin_token}"}
)

if perm_requests.status_code == 200:
    requests_list = perm_requests.json()
    print(f"   Found {len(requests_list)} permission requests")
    
    if requests_list:
        user_to_grant = requests_list[0]
        print(f"\n   First request:")
        print(f"   - User ID: {user_to_grant['id']}")
        print(f"   - Has send_messages: {user_to_grant['has_send_messages']}")
        
        # Step 4: Grant permissions
        print(f"\n4. Granting send_messages permission to user {user_to_grant['id']}...")
        grant_resp = requests.put(
            f"{BASE_URL}/v1/users/{user_to_grant['id']}/permissions",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"permissions": ["send_messages"]}
        )
        
        if grant_resp.status_code == 200:
            print("   Success! Permission granted.")
            user_data = grant_resp.json()
            print(f"   Custom permissions: {user_data.get('custom_permissions', [])}")
        else:
            print(f"   Error {grant_resp.status_code}: {grant_resp.text}")
            
        # Step 5: Verify the grant
        print("\n5. Checking permission requests again...")
        perm_requests2 = requests.get(
            f"{BASE_URL}/v1/users/permission-requests?include_granted=true",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if perm_requests2.status_code == 200:
            for req in perm_requests2.json():
                if req['id'] == user_to_grant['id']:
                    print(f"   User {req['id']} now has send_messages: {req['has_send_messages']}")
                    break
else:
    print(f"   Error: {perm_requests.text}")