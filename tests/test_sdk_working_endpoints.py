#!/usr/bin/env python3
"""
Unit tests for CIRIS SDK endpoints that are currently working.

This file contains only the tests that pass with the current API implementation.
As more endpoints are fixed, tests can be moved from test_sdk_endpoints.py to here.
"""
import asyncio
import pytest
import pytest_asyncio
import socket
from datetime import datetime, timezone

from ciris_sdk import CIRISClient
from ciris_sdk.exceptions import CIRISAuthenticationError, CIRISAPIError


# Skip all tests in this module if API is not available
def check_api_available():
    """Check if API is accessible."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 8080))
        sock.close()
        return result == 0
    except Exception:
        return False


# Apply skip to entire module
pytestmark = pytest.mark.skipif(not check_api_available(), reason="API not running on localhost:8080")


class TestWorkingSDKEndpoints:
    """Tests for SDK endpoints that currently work."""
    
    @pytest_asyncio.fixture
    async def client(self):
        """Create authenticated CIRIS client."""
        async with CIRISClient(base_url="http://localhost:8080", timeout=30.0) as client:
            response = await client.auth.login("admin", "ciris_admin_password")
            # SDK doesn't auto-update transport token yet, so manually set it
            client._transport.set_api_key(response.access_token)
            yield client
    
    @pytest_asyncio.fixture
    async def unauthenticated_client(self):
        """Create unauthenticated CIRIS client."""
        async with CIRISClient(base_url="http://localhost:8080", timeout=30.0) as client:
            yield client

    # ========== Authentication Tests (4 endpoints) ==========
    
    @pytest.mark.asyncio
    async def test_auth_login(self, unauthenticated_client):
        """Test POST /v1/auth/login."""
        # Test successful login
        response = await unauthenticated_client.auth.login("admin", "ciris_admin_password")
        # SDK doesn't auto-update transport token yet, so manually set it
        unauthenticated_client._transport.set_api_key(response.access_token)
        # Check transport has the token
        assert unauthenticated_client._transport.api_key is not None
        assert unauthenticated_client._transport.api_key.startswith("ciris_system_admin_")
        
        # Test failed login - SDK raises generic CIRISAPIError for 401
        from ciris_sdk.exceptions import CIRISAPIError
        with pytest.raises(CIRISAPIError) as exc_info:
            await unauthenticated_client.auth.login("invalid", "wrong")
        assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_auth_logout(self, client):
        """Test POST /v1/auth/logout."""
        # Should succeed with authenticated client
        await client.auth.logout()
        
        # SDK doesn't automatically clear token on logout
        # This would be a nice feature to add in the future
    
    @pytest.mark.asyncio
    async def test_auth_me(self, client):
        """Test GET /v1/auth/me."""
        user_info = await client.auth.get_current_user()
        assert user_info.user_id == "wa-system-admin"
        assert user_info.username == "wa-system-admin"
        assert user_info.role == "SYSTEM_ADMIN"
        assert len(user_info.permissions) > 0
        # Check some expected permissions
        assert "emergency_shutdown" in user_info.permissions
        assert "full_access" in user_info.permissions  # SYSTEM_ADMIN has full_access
    
    @pytest.mark.asyncio
    async def test_auth_refresh(self, client):
        """Test POST /v1/auth/refresh."""
        # Get current token
        old_token = client._transport.api_key
        
        # Refresh token
        response = await client.auth.refresh_token()
        assert response.access_token
        assert response.role == "SYSTEM_ADMIN"
        
        # Manually update client token (SDK should do this automatically in future)
        client._transport.set_api_key(response.access_token)
        
        # Verify new token works
        user_info = await client.auth.get_current_user()
        assert user_info.user_id == "wa-system-admin"

    # ========== System Tests (1 endpoint) ==========
    
    @pytest.mark.asyncio
    async def test_system_health_no_auth(self, unauthenticated_client):
        """Test GET /v1/system/health (no auth required)."""
        health = await unauthenticated_client.system.health()
        assert health.status in ["healthy", "degraded", "critical", "initializing"]
        assert health.version == "1.0.2"
        assert health.uptime_seconds >= 0
        assert hasattr(health, 'services')
        assert health.initialization_complete is True
        assert hasattr(health, 'timestamp')
    
    @pytest.mark.asyncio
    async def test_system_health_with_auth(self, client):
        """Test GET /v1/system/health with authentication."""
        # Should work with auth too
        health = await client.system.health()
        assert health.status in ["healthy", "degraded", "critical"]  # System may be in various states during testing
        assert health.version == "1.0.2"

    # ========== Integration Tests ==========
    
    @pytest.mark.asyncio
    async def test_full_auth_flow(self, unauthenticated_client):
        """Test complete authentication workflow."""
        client = unauthenticated_client
        
        # 1. Clear any existing auth
        client._transport.api_key = None
        
        # 2. Login
        response = await client.auth.login("admin", "ciris_admin_password")
        # SDK doesn't auto-update transport token yet, so manually set it
        client._transport.set_api_key(response.access_token)
        assert client._transport.api_key is not None
        token1 = client._transport.api_key
        
        # 3. Verify authenticated
        user = await client.auth.get_current_user()
        assert user.role == "SYSTEM_ADMIN"
        
        # 4. Refresh token
        response = await client.auth.refresh_token()
        client._transport.set_api_key(response.access_token)
        token2 = client._transport.api_key
        assert token2 != token1
        
        # 5. Verify new token works
        user = await client.auth.get_current_user()
        assert user.role == "SYSTEM_ADMIN"
        
        # 6. Logout
        await client.auth.logout()
        # SDK doesn't automatically clear token on logout
        # The token is invalidated on the server side but still stored locally
        
        # 7. Verify logged out (token is invalid server-side)
        with pytest.raises(CIRISAPIError) as exc_info:
            await client.auth.get_current_user()
        assert exc_info.value.status_code == 401


if __name__ == "__main__":
    # Run only the working tests
    pytest.main([__file__, "-v", "-k", "TestWorkingSDKEndpoints"])