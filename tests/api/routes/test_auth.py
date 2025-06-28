"""
Unit tests for authentication API routes.
"""
import hashlib
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from ciris_engine.schemas.api.auth import (
    UserRole,
    AuthContext,
    Permission,
    ROLE_PERMISSIONS,
)
from ciris_engine.api.services.auth_service import APIAuthService, StoredAPIKey


@pytest.fixture
def mock_auth_service():
    """Create a mock auth service."""
    service = Mock(spec=APIAuthService)
    service.store_api_key = AsyncMock()
    service.validate_api_key = AsyncMock()
    service.revoke_api_key = AsyncMock()
    service.list_api_keys = AsyncMock()
    service.get_api_key_info = AsyncMock()
    service._get_key_id = Mock(return_value="test_key_id")
    return service


@pytest.fixture
def mock_config_service():
    """Create a mock config service."""
    service = Mock()
    service.get_config = AsyncMock()
    return service


@pytest.fixture
def auth_context_root():
    """Create a ROOT auth context."""
    return AuthContext(
        user_id="ROOT",
        role=UserRole.ROOT,
        permissions=ROLE_PERMISSIONS[UserRole.ROOT],
        api_key_id="root_key_123",
        authenticated_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def auth_context_admin():
    """Create an ADMIN auth context."""
    return AuthContext(
        user_id="admin_user",
        role=UserRole.ADMIN,
        permissions=ROLE_PERMISSIONS[UserRole.ADMIN],
        api_key_id="admin_key_456",
        authenticated_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def auth_context_observer():
    """Create an OBSERVER auth context."""
    return AuthContext(
        user_id="observer_user",
        role=UserRole.OBSERVER,
        permissions=ROLE_PERMISSIONS[UserRole.OBSERVER],
        api_key_id="observer_key_789",
        authenticated_at=datetime.now(timezone.utc)
    )


class TestLoginEndpoint:
    """Test /auth/login endpoint."""
    
    @pytest.mark.asyncio
    async def test_login_success(self, mock_auth_service, mock_config_service):
        """Test successful ROOT login."""
        from ciris_engine.api.routes.auth import login
        from ciris_engine.schemas.api.auth import LoginRequest
        
        # Setup mocks
        mock_config_service.get_config.side_effect = [
            "root_user",  # root_username
            hashlib.sha256(b"root_password").hexdigest()  # root_password_hash
        ]
        
        # Create request
        request = LoginRequest(username="root_user", password="root_password")
        
        # Create mock FastAPI request
        mock_request = Mock()
        mock_request.app.state.config_service = mock_config_service
        
        # Execute
        with patch('ciris_engine.api.routes.auth.secrets.token_urlsafe', return_value="test_token"):
            response = await login(request, mock_request, mock_auth_service)
        
        # Verify
        assert response.user_id == "ROOT"
        assert response.role == UserRole.ROOT
        assert response.token_type == "Bearer"
        assert response.expires_in == 86400  # 24 hours
        assert response.access_token.startswith("ciris_root_")
        
        # Verify API key was stored
        mock_auth_service.store_api_key.assert_called_once()
        call_args = mock_auth_service.store_api_key.call_args[1]
        assert call_args['user_id'] == "ROOT"
        assert call_args['role'] == UserRole.ROOT
    
    @pytest.mark.asyncio
    async def test_login_invalid_username(self, mock_auth_service, mock_config_service):
        """Test login with invalid username."""
        from ciris_engine.api.routes.auth import login
        from ciris_engine.schemas.api.auth import LoginRequest
        
        # Setup mocks
        mock_config_service.get_config.side_effect = [
            "root_user",  # root_username
            hashlib.sha256(b"root_password").hexdigest()  # root_password_hash
        ]
        
        # Create request with wrong username
        request = LoginRequest(username="wrong_user", password="root_password")
        
        # Create mock FastAPI request
        mock_request = Mock()
        mock_request.app.state.config_service = mock_config_service
        
        # Execute and verify exception
        with pytest.raises(HTTPException) as exc_info:
            await login(request, mock_request, mock_auth_service)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid credentials"
    
    @pytest.mark.asyncio
    async def test_login_invalid_password(self, mock_auth_service, mock_config_service):
        """Test login with invalid password."""
        from ciris_engine.api.routes.auth import login
        from ciris_engine.schemas.api.auth import LoginRequest
        
        # Setup mocks
        mock_config_service.get_config.side_effect = [
            "root_user",  # root_username
            hashlib.sha256(b"root_password").hexdigest()  # root_password_hash
        ]
        
        # Create request with wrong password
        request = LoginRequest(username="root_user", password="wrong_password")
        
        # Create mock FastAPI request
        mock_request = Mock()
        mock_request.app.state.config_service = mock_config_service
        
        # Execute and verify exception
        with pytest.raises(HTTPException) as exc_info:
            await login(request, mock_request, mock_auth_service)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid credentials"
    
    @pytest.mark.asyncio
    async def test_login_no_config_service(self, mock_auth_service):
        """Test login when config service is not available."""
        from ciris_engine.api.routes.auth import login
        from ciris_engine.schemas.api.auth import LoginRequest
        
        # Create request
        request = LoginRequest(username="root_user", password="root_password")
        
        # Create mock FastAPI request without config service
        mock_request = Mock()
        mock_request.app.state.config_service = None
        
        # Execute and verify exception
        with pytest.raises(HTTPException) as exc_info:
            await login(request, mock_request, mock_auth_service)
        
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Configuration service not available"
    
    @pytest.mark.asyncio
    async def test_login_no_root_credentials(self, mock_auth_service, mock_config_service):
        """Test login when ROOT credentials are not configured."""
        from ciris_engine.api.routes.auth import login
        from ciris_engine.schemas.api.auth import LoginRequest
        
        # Setup mocks to return None
        mock_config_service.get_config.side_effect = [None, None]
        
        # Create request
        request = LoginRequest(username="root_user", password="root_password")
        
        # Create mock FastAPI request
        mock_request = Mock()
        mock_request.app.state.config_service = mock_config_service
        
        # Execute and verify exception
        with pytest.raises(HTTPException) as exc_info:
            await login(request, mock_request, mock_auth_service)
        
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "ROOT credentials not configured"


class TestLogoutEndpoint:
    """Test /auth/logout endpoint."""
    
    @pytest.mark.asyncio
    async def test_logout_success(self, mock_auth_service, auth_context_root):
        """Test successful logout."""
        from ciris_engine.api.routes.auth import logout
        
        # Execute
        result = await logout(auth_context_root, mock_auth_service)
        
        # Verify
        assert result is None
        mock_auth_service.revoke_api_key.assert_called_once_with("root_key_123")
    
    @pytest.mark.asyncio
    async def test_logout_no_api_key_id(self, mock_auth_service):
        """Test logout when auth context has no API key ID."""
        from ciris_engine.api.routes.auth import logout
        
        # Create auth context without api_key_id
        auth_context = AuthContext(
            user_id="test_user",
            role=UserRole.ADMIN,
            permissions=set(),
            api_key_id=None,
            authenticated_at=datetime.now(timezone.utc)
        )
        
        # Execute
        result = await logout(auth_context, mock_auth_service)
        
        # Verify no revocation was attempted
        assert result is None
        mock_auth_service.revoke_api_key.assert_not_called()


class TestGetCurrentUserEndpoint:
    """Test /auth/me endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_current_user_root(self, auth_context_root):
        """Test getting current user info for ROOT."""
        from ciris_engine.api.routes.auth import get_current_user
        
        # Execute
        result = await get_current_user(auth_context_root)
        
        # Verify
        assert result.user_id == "ROOT"
        assert result.username == "ROOT"
        assert result.role == UserRole.ROOT
        # ROOT should have all permissions
        assert len(result.permissions) == len(Permission)
        assert Permission.FULL_ACCESS.value in result.permissions
        assert Permission.EMERGENCY_SHUTDOWN.value in result.permissions
        assert result.created_at == auth_context_root.authenticated_at
        assert result.last_login == auth_context_root.authenticated_at
    
    @pytest.mark.asyncio
    async def test_get_current_user_admin(self, auth_context_admin):
        """Test getting current user info for ADMIN."""
        from ciris_engine.api.routes.auth import get_current_user
        
        # Execute
        result = await get_current_user(auth_context_admin)
        
        # Verify
        assert result.user_id == "admin_user"
        assert result.username == "admin_user"
        assert result.role == UserRole.ADMIN
        assert Permission.RUNTIME_CONTROL.value in result.permissions
        assert Permission.RESOLVE_DEFERRALS.value not in result.permissions
    
    @pytest.mark.asyncio
    async def test_get_current_user_observer(self, auth_context_observer):
        """Test getting current user info for OBSERVER."""
        from ciris_engine.api.routes.auth import get_current_user
        
        # Execute
        result = await get_current_user(auth_context_observer)
        
        # Verify
        assert result.user_id == "observer_user"
        assert result.username == "observer_user"
        assert result.role == UserRole.OBSERVER
        assert Permission.VIEW_MESSAGES.value in result.permissions
        assert Permission.RUNTIME_CONTROL.value not in result.permissions


# Permissions endpoint removed - now included in /auth/me response


class TestRefreshTokenEndpoint:
    """Test /auth/refresh endpoint."""
    
    @pytest.mark.asyncio
    async def test_refresh_token_success_root(self, mock_auth_service, auth_context_root):
        """Test successful token refresh for ROOT."""
        from ciris_engine.api.routes.auth import refresh_token
        from ciris_engine.schemas.api.auth import TokenRefreshRequest
        
        # Create request
        request = TokenRefreshRequest(refresh_token="dummy_refresh_token")
        
        # Execute
        with patch('ciris_engine.api.routes.auth.secrets.token_urlsafe', return_value="new_token"):
            response = await refresh_token(request, auth_context_root, mock_auth_service)
        
        # Verify
        assert response.user_id == "ROOT"
        assert response.role == UserRole.ROOT
        assert response.expires_in == 86400  # 24 hours for ROOT
        assert response.access_token.startswith("ciris_root_")
        
        # Verify old key was revoked and new key stored
        mock_auth_service.revoke_api_key.assert_called_once_with("root_key_123")
        mock_auth_service.store_api_key.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_refresh_token_success_admin(self, mock_auth_service, auth_context_admin):
        """Test successful token refresh for ADMIN."""
        from ciris_engine.api.routes.auth import refresh_token
        from ciris_engine.schemas.api.auth import TokenRefreshRequest
        
        # Create request
        request = TokenRefreshRequest(refresh_token="dummy_refresh_token")
        
        # Execute
        with patch('ciris_engine.api.routes.auth.secrets.token_urlsafe', return_value="new_token"):
            response = await refresh_token(request, auth_context_admin, mock_auth_service)
        
        # Verify
        assert response.user_id == "admin_user"
        assert response.role == UserRole.ADMIN
        assert response.expires_in == 2592000  # 30 days for non-ROOT
        assert response.access_token.startswith("ciris_admin_")
    
    @pytest.mark.asyncio
    async def test_refresh_token_no_auth(self, mock_auth_service):
        """Test token refresh without authentication."""
        from ciris_engine.api.routes.auth import refresh_token
        from ciris_engine.schemas.api.auth import TokenRefreshRequest
        
        # Create request
        request = TokenRefreshRequest(refresh_token="dummy_refresh_token")
        
        # Execute and verify exception
        with pytest.raises(HTTPException) as exc_info:
            await refresh_token(request, None, mock_auth_service)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Authentication required to refresh token"
    
    @pytest.mark.asyncio
    async def test_refresh_token_no_old_key_id(self, mock_auth_service):
        """Test token refresh when auth context has no API key ID."""
        from ciris_engine.api.routes.auth import refresh_token
        from ciris_engine.schemas.api.auth import TokenRefreshRequest
        
        # Create auth context without api_key_id
        auth_context = AuthContext(
            user_id="test_user",
            role=UserRole.ADMIN,
            permissions=set(),
            api_key_id=None,
            authenticated_at=datetime.now(timezone.utc)
        )
        
        # Create request
        request = TokenRefreshRequest(refresh_token="dummy_refresh_token")
        
        # Execute
        with patch('ciris_engine.api.routes.auth.secrets.token_urlsafe', return_value="new_token"):
            response = await refresh_token(request, auth_context, mock_auth_service)
        
        # Verify new key was created but no old key revoked
        mock_auth_service.store_api_key.assert_called_once()
        mock_auth_service.revoke_api_key.assert_not_called()