#!/usr/bin/env python3
import requests
import json

BASE_URL = "http://localhost:8080"

# Login as admin
login_resp = requests.post(
    f"{BASE_URL}/v1/auth/login",
    json={"username": "admin", "password": "ciris_admin_password"}
)
admin_token = login_resp.json()["access_token"]

# Check permission requests
perm_requests_resp = requests.get(
    f"{BASE_URL}/v1/users/permission-requests",
    headers={"Authorization": f"Bearer {admin_token}"}
)
print(f"Status: {perm_requests_resp.status_code}")
print(f"Response: {json.dumps(perm_requests_resp.json(), indent=2)}")

# Also check the user details
users_resp = requests.get(
    f"{BASE_URL}/v1/users",
    headers={"Authorization": f"Bearer {admin_token}"}
)
print("\nAll users:")
for user in users_resp.json()["items"]:
    print(f"- {user['username']} ({user['user_id']}): permission_requested_at={user.get('permission_requested_at')}")