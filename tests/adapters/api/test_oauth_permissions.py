"""
OAuth Permission System Tests

Tests the complete OAuth user permission workflow:
1. OAuth user creation
2. Permission requests
3. Admin permission grants
4. Access control enforcement
"""
import pytest
import pytest_asyncio
from unittest.mock import Mock, patch
import secrets
from datetime import datetime, timezone
from httpx import AsyncClient
from fastapi import status

from ciris_engine.logic.adapters.api.app import create_app
from ciris_engine.logic.adapters.api.services.auth_service import APIAuthService, OAuthUser, UserRole
from ciris_engine.logic.runtime.ciris_runtime import CIRISRuntime
from ciris_engine.logic.runtime.prevent_sideeffects import allow_runtime_creation
from ciris_engine.schemas.config.essential import EssentialConfig


@pytest_asyncio.fixture
async def test_runtime():
    """Create a test runtime for OAuth testing."""
    # Allow runtime creation in tests
    allow_runtime_creation()
    
    config = EssentialConfig()
    config.services.llm_endpoint = "mock://localhost"
    config.services.llm_model = "mock"
    
    runtime = CIRISRuntime(
        adapter_types=["api"],
        essential_config=config,
        startup_channel_id="test_oauth",
        mock_llm=True
    )
    
    await runtime.initialize()
    yield runtime
    await runtime.shutdown()


@pytest.fixture
def oauth_test_app(test_runtime):
    """Create test app with OAuth support."""
    app = create_app(test_runtime)
    return app


@pytest.fixture
async def oauth_client(oauth_test_app):
    """Create async test client."""
    async with AsyncClient(app=oauth_test_app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def admin_token(oauth_client):
    """Get admin authentication token."""
    response = await oauth_client.post(
        "/v1/auth/login",
        json={"username": "admin", "password": "ciris_admin_password"}
    )
    assert response.status_code == status.HTTP_200_OK
    return response.json()["access_token"]


@pytest.fixture
async def oauth_user(oauth_client):
    """Create an OAuth user for testing."""
    # Simulate OAuth user creation (normally done in OAuth callback)
    auth_service = APIAuthService()
    
    external_id = f"google-user-{secrets.token_hex(8)}"
    email = f"testuser.{secrets.token_hex(4)}@gmail.com"
    name = "Test OAuth User"
    picture = "https://lh3.googleusercontent.com/a/ACg8ocKt3P4yBmK8sLB2uPCmpvR0N7V_ybpGmQ"
    
    oauth_user = auth_service.create_oauth_user(
        provider="google",
        external_id=external_id,
        email=email,
        name=name,
        picture=picture,
        api_role=UserRole.OBSERVER,
        wa_role=UserRole.OBSERVER
    )
    
    # Generate API key for the user
    api_key = f"ciris_observer_test_oauth_key_{secrets.token_hex(8)}"
    auth_service.store_api_key(
        key=api_key,
        user_id=oauth_user.user_id,
        role=oauth_user.role,
        description="OAuth login via google"
    )
    
    return {
        "user": oauth_user,
        "api_key": api_key,
        "email": email,
        "name": name
    }


class TestOAuthPermissions:
    """Test OAuth permission request and grant workflow."""
    
    async def test_oauth_user_creation(self, oauth_client, admin_token, oauth_user):
        """Test that OAuth users are created correctly."""
        # Check user appears in user list
        response = await oauth_client.get(
            "/v1/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        
        users = response.json()["items"]
        oauth_user_found = False
        for user in users:
            if user["user_id"] == oauth_user["user"].user_id:
                oauth_user_found = True
                assert user["oauth_provider"] == "google"
                assert user["oauth_email"] == oauth_user["email"]
                assert user["oauth_name"] == oauth_user["name"]
                assert user["oauth_picture"] == oauth_user["user"].oauth_picture
                break
        
        assert oauth_user_found, "OAuth user not found in user list"
    
    async def test_oauth_user_denied_without_permission(self, oauth_client, oauth_user):
        """Test that OAuth users cannot interact without permission."""
        # Try to interact without permission
        response = await oauth_client.post(
            "/v1/agent/interact",
            headers={"Authorization": f"Bearer {oauth_user['api_key']}"},
            json={
                "message": "Hello",
                "channel_id": f"api_oauth_{oauth_user['user'].user_id}"
            }
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Permission required" in response.json()["detail"]
    
    async def test_permission_request_creation(self, oauth_client, oauth_user):
        """Test that permission requests are created when OAuth users try to interact."""
        # First interaction attempt creates permission request
        await oauth_client.post(
            "/v1/agent/interact",
            headers={"Authorization": f"Bearer {oauth_user['api_key']}"},
            json={
                "message": "Hello",
                "channel_id": f"api_oauth_{oauth_user['user'].user_id}"
            }
        )
        
        # Get current user to check permission request
        response = await oauth_client.get(
            "/v1/auth/current",
            headers={"Authorization": f"Bearer {oauth_user['api_key']}"}
        )
        assert response.status_code == status.HTTP_200_OK
        
        current = response.json()
        assert current["permission_request"] is not None
        assert current["permission_request"]["status"] == "pending"
        assert current["permission_request"]["api_permission"] == "requested"
        assert current["permission_request"]["wa_permission"] == "not_requested"
    
    async def test_admin_view_permission_requests(self, oauth_client, admin_token, oauth_user):
        """Test that admins can view permission requests."""
        # Create permission request
        await oauth_client.post(
            "/v1/agent/interact",
            headers={"Authorization": f"Bearer {oauth_user['api_key']}"},
            json={
                "message": "Hello",
                "channel_id": f"api_oauth_{oauth_user['user'].user_id}"
            }
        )
        
        # Admin views permission requests
        response = await oauth_client.get(
            "/v1/users/permission-requests",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        
        requests = response.json()["items"]
        found = False
        for req in requests:
            if req["user_id"] == oauth_user["user"].user_id:
                found = True
                assert req["status"] == "pending"
                assert req["api_permission"] == "requested"
                assert req["oauth_provider"] == "google"
                assert req["oauth_email"] == oauth_user["email"]
                break
        
        assert found, "Permission request not found"
    
    async def test_admin_grant_permission(self, oauth_client, admin_token, oauth_user):
        """Test that admins can grant permissions to OAuth users."""
        # Create permission request
        await oauth_client.post(
            "/v1/agent/interact",
            headers={"Authorization": f"Bearer {oauth_user['api_key']}"},
            json={
                "message": "Hello",
                "channel_id": f"api_oauth_{oauth_user['user'].user_id}"
            }
        )
        
        # Admin grants API permission
        response = await oauth_client.post(
            f"/v1/users/{oauth_user['user'].user_id}/grant-permissions",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "api_permission": True,
                "wa_permission": False,
                "reason": "Test user approved"
            }
        )
        assert response.status_code == status.HTTP_200_OK
        
        result = response.json()
        assert result["status"] == "approved"
        assert result["api_permission"] == "granted"
        assert result["wa_permission"] == "not_requested"
    
    async def test_oauth_user_can_interact_after_permission(self, oauth_client, admin_token, oauth_user):
        """Test that OAuth users can interact after permission is granted."""
        # Create permission request
        await oauth_client.post(
            "/v1/agent/interact",
            headers={"Authorization": f"Bearer {oauth_user['api_key']}"},
            json={
                "message": "Hello",
                "channel_id": f"api_oauth_{oauth_user['user'].user_id}"
            }
        )
        
        # Admin grants permission
        await oauth_client.post(
            f"/v1/users/{oauth_user['user'].user_id}/grant-permissions",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "api_permission": True,
                "wa_permission": False,
                "reason": "Test user approved"
            }
        )
        
        # Now user can interact successfully
        response = await oauth_client.post(
            "/v1/agent/interact",
            headers={"Authorization": f"Bearer {oauth_user['api_key']}"},
            json={
                "message": "Hello CIRIS",
                "channel_id": f"api_oauth_{oauth_user['user'].user_id}"
            }
        )
        assert response.status_code == status.HTTP_200_OK
        assert "request_id" in response.json()
    
    async def test_oauth_permission_persistence(self, oauth_client, admin_token, oauth_user):
        """Test that permissions persist across sessions."""
        # Grant permission
        await oauth_client.post(
            "/v1/agent/interact",
            headers={"Authorization": f"Bearer {oauth_user['api_key']}"},
            json={
                "message": "Hello",
                "channel_id": f"api_oauth_{oauth_user['user'].user_id}"
            }
        )
        
        await oauth_client.post(
            f"/v1/users/{oauth_user['user'].user_id}/grant-permissions",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "api_permission": True,
                "wa_permission": False,
                "reason": "Test user approved"
            }
        )
        
        # Check current user shows granted permission
        response = await oauth_client.get(
            "/v1/auth/current",
            headers={"Authorization": f"Bearer {oauth_user['api_key']}"}
        )
        assert response.status_code == status.HTTP_200_OK
        
        current = response.json()
        assert current["permission_request"] is not None
        assert current["permission_request"]["status"] == "approved"
        assert current["permission_request"]["api_permission"] == "granted"