#!/usr/bin/env python3
"""
Test complete OAuth permission request flow.
This simulates what happens when a real OAuth user logs in and requests permissions.
"""
import requests
import json
import secrets

BASE_URL = "http://localhost:8080"

print("=== OAuth Permission Request System Test ===\n")

# Step 1: Admin login
print("1. Admin login...")
admin_resp = requests.post(
    f"{BASE_URL}/v1/auth/login",
    json={"username": "admin", "password": "ciris_admin_password"}
)
admin_token = admin_resp.json()["access_token"]
print(f"   Admin token: {admin_token[:20]}...")

# Step 2: Simulate OAuth callback (this is what happens when user logs in via OAuth)
print("\n2. Simulating Google OAuth callback...")
# In production, this would be called by the OAuth provider with a real auth code
# For testing, we'll call the auth service directly

# First, we need to manually create an OAuth user since we can't do real OAuth
# This simulates what the OAuth callback endpoint does
import sys
import os
sys.path.insert(0, '/app' if os.path.exists('/app') else '.')

try:
    from ciris_engine.logic.adapters.api.services.auth_service import APIAuthService, OAuthUser, UserRole
    from ciris_engine.logic.adapters.api.services.oauth_security import validate_oauth_picture_url
    from datetime import datetime, timezone, timedelta
    
    # Create auth service instance
    auth_service = APIAuthService()
    
    # Simulate OAuth user creation (this is what happens in the OAuth callback)
    external_id = f"google-user-{secrets.token_hex(8)}"
    email = f"testuser.{secrets.token_hex(4)}@gmail.com"
    name = "Test OAuth User"
    picture = "https://lh3.googleusercontent.com/a/ACg8ocKt3P4yBmK8sLB2uPCmpvR0N7V_ybpGmQ"
    
    oauth_user = auth_service.create_oauth_user(
        provider="google",
        external_id=external_id,
        email=email,
        name=name,
        role=UserRole.OBSERVER
    )
    
    print(f"   Created OAuth user: {oauth_user.user_id}")
    print(f"   Email: {email}")
    print(f"   Name: {name}")
    
    # Store OAuth profile data (this happens in the OAuth callback)
    if validate_oauth_picture_url(picture):
        user = auth_service.get_user(oauth_user.user_id)
        if user:
            user.oauth_name = name
            user.oauth_picture = picture
            auth_service._users[oauth_user.user_id] = user
            print(f"   Profile picture validated and stored")
    
    # Generate API key for the OAuth user
    api_key = f"ciris_observer_{secrets.token_urlsafe(32)}"
    auth_service.store_api_key(
        key=api_key,
        user_id=oauth_user.user_id,
        role=oauth_user.role,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        description="OAuth login via google"
    )
    
    oauth_token = api_key
    print(f"   OAuth user token: {oauth_token[:20]}...")
    
except ImportError:
    print("   ERROR: Running outside container, simulating with regular user")
    # Fallback: create a regular user
    create_resp = requests.post(
        f"{BASE_URL}/v1/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "username": f"oauth_sim_{secrets.token_hex(4)}",
            "password": "test12345",
            "api_role": "OBSERVER"
        }
    )
    user_data = create_resp.json()
    oauth_user_id = user_data["user_id"]
    
    # Login as the user
    login_resp = requests.post(
        f"{BASE_URL}/v1/auth/login",
        json={"username": user_data["username"], "password": "test12345"}
    )
    oauth_token = login_resp.json()["access_token"]
    oauth_user = type('obj', (object,), {'user_id': oauth_user_id})
    email = "simulated@example.com"
    name = "Simulated User"

# Step 3: OAuth user tries to send a message (should fail)
print("\n3. OAuth user tries to interact with agent...")
interact_resp = requests.post(
    f"{BASE_URL}/v1/agent/interact",
    headers={"Authorization": f"Bearer {oauth_token}"},
    json={"message": "Hello CIRIS!", "channel_id": "api_test"}
)

if interact_resp.status_code == 403:
    error_data = interact_resp.json()
    print(f"   Expected 403 error: {error_data['error']}")
    print(f"   Discord invite: {error_data.get('discord_invite', 'Not set')}")
    print(f"   Can request permissions: {error_data.get('can_request_permissions', False)}")
else:
    print(f"   Unexpected status: {interact_resp.status_code}")

# Step 4: OAuth user requests permissions
print("\n4. OAuth user requests permissions...")
perm_req_resp = requests.post(
    f"{BASE_URL}/v1/users/request-permissions",
    headers={"Authorization": f"Bearer {oauth_token}"}
)

if perm_req_resp.status_code == 200:
    req_data = perm_req_resp.json()
    print(f"   Success: {req_data['success']}")
    print(f"   Status: {req_data['status']}")
    print(f"   Message: {req_data['message']}")
    print(f"   Requested at: {req_data['requested_at']}")
else:
    print(f"   ERROR: {perm_req_resp.text}")

# Step 5: Check permission requests as admin
print("\n5. Admin checks permission requests...")
perm_list_resp = requests.get(
    f"{BASE_URL}/v1/users/permission-requests",
    headers={"Authorization": f"Bearer {admin_token}"}
)

if perm_list_resp.status_code == 200:
    requests_list = perm_list_resp.json()
    print(f"   Found {len(requests_list)} permission requests")
    
    for req in requests_list:
        if req['id'] == oauth_user.user_id:
            print(f"\n   Request from our OAuth user:")
            print(f"   - ID: {req['id']}")
            print(f"   - Email: {req['email']}")
            print(f"   - Name: {req['oauth_name']}")
            print(f"   - Picture: {req['oauth_picture']}")
            print(f"   - Requested at: {req['permission_requested_at']}")
            print(f"   - Already has permission: {req['has_send_messages']}")
            break
else:
    print(f"   ERROR: {perm_list_resp.text}")

# Step 6: Grant permissions to the user
print("\n6. Admin grants SEND_MESSAGES permission...")
# First check who can grant permissions
print("   Checking admin permissions...")
me_resp = requests.get(
    f"{BASE_URL}/v1/auth/me",
    headers={"Authorization": f"Bearer {admin_token}"}
)
admin_perms = me_resp.json().get("permissions", [])
if "manage_user_permissions" in admin_perms:
    print("   Admin has manage_user_permissions permission")
else:
    print(f"   Admin permissions: {admin_perms}")
    print("   Admin lacks manage_user_permissions - this is a SYSTEM_ADMIN permission")
    
grant_resp = requests.put(
    f"{BASE_URL}/v1/users/{oauth_user.user_id}/permissions",
    headers={"Authorization": f"Bearer {admin_token}"},
    json={"permissions": ["send_messages"]}
)

if grant_resp.status_code == 200:
    print(f"   Permissions granted successfully")
else:
    print(f"   ERROR: {grant_resp.text}")

# Step 7: OAuth user tries to interact again (should succeed)
print("\n7. OAuth user tries to interact again...")
interact_resp2 = requests.post(
    f"{BASE_URL}/v1/agent/interact",
    headers={"Authorization": f"Bearer {oauth_token}"},
    json={"message": "$speak Hello CIRIS! I now have permission!", "channel_id": "api_test"}
)

if interact_resp2.status_code == 200:
    response_data = interact_resp2.json()
    print(f"   Success! Response:")
    print(f"   - Status: {response_data['status']}")
    print(f"   - Message: {response_data.get('message', 'No message')}")
    print(f"   - Content: {response_data.get('content', 'No content')}")
else:
    print(f"   ERROR {interact_resp2.status_code}: {interact_resp2.text}")

# Step 8: Check permission requests again (with include_granted=true)
print("\n8. Check permission requests including granted ones...")
perm_list_resp2 = requests.get(
    f"{BASE_URL}/v1/users/permission-requests?include_granted=true",
    headers={"Authorization": f"Bearer {admin_token}"}
)

if perm_list_resp2.status_code == 200:
    requests_list = perm_list_resp2.json()
    for req in requests_list:
        if req['id'] == oauth_user.user_id:
            print(f"   User now has send_messages: {req['has_send_messages']}")
            break

print("\n=== Test Complete ===")