#\!/usr/bin/env python3
"""
Test script to simulate OAuth user creation and permission request flow.
"""
import requests
import json
import time

BASE_URL = "http://localhost:8080"

# Step 1: Login as admin to get token
print("1. Logging in as admin...")
login_resp = requests.post(
    f"{BASE_URL}/v1/auth/login",
    json={"username": "admin", "password": "ciris_admin_password"}
)
admin_token = login_resp.json()["access_token"]
print(f"   Got admin token: {admin_token[:20]}...")

# Step 2: Create a test user with OBSERVER role
print("\n2. Creating test OAuth user...")
create_user_resp = requests.post(
    f"{BASE_URL}/v1/users",
    headers={"Authorization": f"Bearer {admin_token}"},
    json={
        "username": "test_oauth_user",
        "password": "test_password",
        "api_role": "OBSERVER"
    }
)
if create_user_resp.status_code == 200:
    print("   Test user created successfully")
else:
    print(f"   Error creating user: {create_user_resp.text}")

# Step 3: Login as the test user
print("\n3. Logging in as test user...")
test_login_resp = requests.post(
    f"{BASE_URL}/v1/auth/login",
    json={"username": "test_oauth_user", "password": "test_password"}
)
test_token = test_login_resp.json()["access_token"]
print(f"   Got test user token: {test_token[:20]}...")

# Step 4: Try to interact (should fail with 403)
print("\n4. Testing interact endpoint (should fail)...")
interact_resp = requests.post(
    f"{BASE_URL}/v1/agent/interact",
    headers={"Authorization": f"Bearer {test_token}"},
    json={"message": "Hello\!"}
)
if interact_resp.status_code == 403:
    print("   ✓ Got expected 403 error:")
    print(f"   {json.dumps(interact_resp.json(), indent=2)}")
else:
    print(f"   Unexpected status: {interact_resp.status_code}")

# Step 5: Request permissions
print("\n5. Requesting permissions...")
request_perm_resp = requests.post(
    f"{BASE_URL}/v1/users/request-permissions",
    headers={"Authorization": f"Bearer {test_token}"}
)
print(f"   Response: {json.dumps(request_perm_resp.json(), indent=2)}")

# Step 6: Check permission requests as admin
print("\n6. Checking permission requests (as admin)...")
perm_requests_resp = requests.get(
    f"{BASE_URL}/v1/users/permission-requests",
    headers={"Authorization": f"Bearer {admin_token}"}
)
print(f"   Permission requests: {json.dumps(perm_requests_resp.json(), indent=2)}")

# Step 7: Grant permissions
if perm_requests_resp.status_code == 200 and perm_requests_resp.json():
    user_id = perm_requests_resp.json()[0]["id"]
    print(f"\n7. Granting SEND_MESSAGES permission to user {user_id}...")
    grant_resp = requests.patch(
        f"{BASE_URL}/v1/users/{user_id}/permissions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"grant_permissions": ["SEND_MESSAGES"]}
    )
    print(f"   Response: {grant_resp.status_code}")

# Step 8: Try to interact again (should work now)
print("\n8. Testing interact endpoint again (should work)...")
interact_resp2 = requests.post(
    f"{BASE_URL}/v1/agent/interact",
    headers={"Authorization": f"Bearer {test_token}"},
    json={"message": "Hello after permission grant\!"}
)
print(f"   Status: {interact_resp2.status_code}")
if interact_resp2.status_code == 200:
    print("   ✓ Success\! User can now send messages")
    print(f"   Response: {json.dumps(interact_resp2.json(), indent=2)}")

