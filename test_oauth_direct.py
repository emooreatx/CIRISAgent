#!/usr/bin/env python3
"""
Direct test of OAuth user creation and permission request flow.
This simulates what happens in the OAuth callback without going through actual OAuth.
"""
import requests
import json
import sys
import os

# Add the app directory to Python path so we can import modules
sys.path.insert(0, '/app')

from ciris_engine.logic.adapters.api.services.auth_service import APIAuthService, OAuthUser, UserRole
from datetime import datetime, timezone

print("1. Creating auth service and OAuth user directly...")

# Create an auth service instance
auth_service = APIAuthService()

# Simulate OAuth user creation (this is what happens in the OAuth callback)
oauth_user = auth_service.create_oauth_user(
    provider="google",
    external_id="test-user-12345",
    email="testuser@example.com",
    name="Test OAuth User",
    role=UserRole.OBSERVER
)

print(f"   Created OAuth user: {oauth_user.user_id}")

# Simulate storing OAuth profile data
user = auth_service.get_user(oauth_user.user_id)
if user:
    user.oauth_name = "Test OAuth User"
    user.oauth_picture = "https://lh3.googleusercontent.com/test-avatar.png"
    # Store the updated user
    auth_service._users[oauth_user.user_id] = user
    print(f"   Updated user with OAuth profile data")

# Generate an API key for the user (this also happens in OAuth callback)
api_key = f"ciris_observer_test_oauth_key_12345"
auth_service.store_api_key(
    key=api_key,
    user_id=oauth_user.user_id,
    role=oauth_user.role,
    description="OAuth login via google"
)

print(f"   Generated API key for user")

# Now test via API
BASE_URL = "http://localhost:8080"

# Login as admin to check things
print("\n2. Logging in as admin...")
login_resp = requests.post(
    f"{BASE_URL}/v1/auth/login",
    json={"username": "admin", "password": "ciris_admin_password"}
)
admin_token = login_resp.json()["access_token"]

# Check if our OAuth user appears in the user list
print("\n3. Checking if OAuth user appears in user list...")
users_resp = requests.get(
    f"{BASE_URL}/v1/users",
    headers={"Authorization": f"Bearer {admin_token}"}
)

oauth_user_found = False
for user in users_resp.json()["items"]:
    if "google:" in user["user_id"]:
        print(f"   Found OAuth user: {user['user_id']} - {user['username']}")
        oauth_user_found = True
        print(f"   OAuth fields: name={user.get('oauth_name')}, picture={user.get('oauth_picture')}")

if not oauth_user_found:
    print("   OAuth user not found in API response!")
    
print("\nNote: Since we're directly manipulating the auth service,")
print("the changes might not persist across API calls.")
print("In production, OAuth users are created through the /auth/oauth/{provider}/callback endpoint.")