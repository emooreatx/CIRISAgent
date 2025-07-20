#!/usr/bin/env python3
"""
Test OAuth user simulation with proper data storage.
"""
import requests
import json

BASE_URL = "http://localhost:8080"

# Step 1: Simulate OAuth callback (without actual OAuth)
print("1. Simulating OAuth callback...")

# We'll need to directly interact with the auth service to simulate an OAuth user
# For now, let's create a regular user and manually update their fields

# Login as admin first
login_resp = requests.post(
    f"{BASE_URL}/v1/auth/login",
    json={"username": "admin", "password": "ciris_admin_password"}
)
admin_token = login_resp.json()["access_token"]
print(f"   Admin token: {admin_token[:20]}...")

# Create a test OAuth-like user
print("\n2. Creating test OAuth user...")
create_resp = requests.post(
    f"{BASE_URL}/v1/users",
    headers={"Authorization": f"Bearer {admin_token}"},
    json={
        "username": "oauth_test_user",
        "password": "test12345",
        "api_role": "OBSERVER"
    }
)

if create_resp.status_code == 200:
    user_data = create_resp.json()
    user_id = user_data["user_id"]
    print(f"   Created user: {user_id}")
else:
    print(f"   Error: {create_resp.text}")
    exit(1)

# Login as the test user
print("\n3. Logging in as OAuth test user...")
user_login_resp = requests.post(
    f"{BASE_URL}/v1/auth/login",
    json={"username": "oauth_test_user", "password": "test12345"}
)
user_token = user_login_resp.json()["access_token"]
print(f"   User token: {user_token[:20]}...")

# Get user details to confirm state
print("\n4. Getting user details...")
user_details = requests.get(
    f"{BASE_URL}/v1/users/{user_id}",
    headers={"Authorization": f"Bearer {admin_token}"}
)
print(f"   User details: {json.dumps(user_details.json(), indent=2)}")

# Request permissions as the user
print("\n5. Requesting permissions as user...")
perm_request_resp = requests.post(
    f"{BASE_URL}/v1/users/request-permissions",
    headers={"Authorization": f"Bearer {user_token}"}
)
print(f"   Response: {json.dumps(perm_request_resp.json(), indent=2)}")

# Check permission requests as admin
print("\n6. Checking permission requests as admin...")
perm_list_resp = requests.get(
    f"{BASE_URL}/v1/users/permission-requests",
    headers={"Authorization": f"Bearer {admin_token}"}
)
print(f"   Status: {perm_list_resp.status_code}")
print(f"   Response: {json.dumps(perm_list_resp.json(), indent=2)}")

# If we got results, let's check the users endpoint too
print("\n7. Checking all users to see permission_requested_at...")
all_users_resp = requests.get(
    f"{BASE_URL}/v1/users",
    headers={"Authorization": f"Bearer {admin_token}"}
)
for user in all_users_resp.json()["items"]:
    if user.get("permission_requested_at"):
        print(f"   - {user['username']}: requested at {user['permission_requested_at']}")