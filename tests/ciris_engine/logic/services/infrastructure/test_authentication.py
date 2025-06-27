"""Unit tests for AuthenticationService."""

import pytest
import jwt
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from ciris_engine.logic.services.infrastructure.authentication import AuthenticationService
from ciris_engine.schemas.services.authority_core import (
    WACertificate, ChannelIdentity, AuthorizationContext, 
    WARole, TokenType, JWTSubType
)
from ciris_engine.schemas.services.authority.wise_authority import (
    AuthenticationResult, WAUpdate, TokenVerification
)
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus


class TestAuthenticationService:
    """Test cases for AuthenticationService."""
    
    @pytest.fixture
    def mock_time_service(self):
        """Create mock time service."""
        current_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        return Mock(
            now=Mock(return_value=current_time),
            now_iso=Mock(return_value=current_time.isoformat())
        )
    
    @pytest.fixture
    def mock_secrets_service(self):
        """Create mock secrets service."""
        return Mock(
            get_secret=Mock(return_value="test-secret-key-for-jwt-signing"),
            encrypt=Mock(side_effect=lambda x: f"encrypted:{x}"),
            decrypt=Mock(side_effect=lambda x: x.replace("encrypted:", ""))
        )
    
    @pytest.fixture
    def auth_service(self, mock_time_service, mock_secrets_service):
        """Create AuthenticationService instance."""
        service = AuthenticationService(
            time_service=mock_time_service,
            secrets_service=mock_secrets_service,
            token_expiry_hours=24,
            refresh_token_days=7
        )
        return service
    
    @pytest.mark.asyncio
    async def test_start_stop(self, auth_service):
        """Test service start and stop."""
        # Start
        await auth_service.start()
        assert auth_service._running is True
        
        # Stop
        await auth_service.stop()
        assert auth_service._running is False
    
    @pytest.mark.asyncio
    async def test_create_token(self, auth_service):
        """Test creating an auth token."""
        await auth_service.start()
        
        token = await auth_service.create_token(
            user_id="user123",
            permissions=["read", "write"],
            metadata={"source": "api"}
        )
        
        assert isinstance(token, AuthToken)
        assert token.user_id == "user123"
        assert token.permissions == ["read", "write"]
        assert token.token_type == TokenType.ACCESS
        assert len(token.token) > 0
        assert len(token.refresh_token) > 0
    
    @pytest.mark.asyncio
    async def test_verify_valid_token(self, auth_service):
        """Test verifying a valid token."""
        await auth_service.start()
        
        # Create token
        token = await auth_service.create_token(
            user_id="user123",
            permissions=["read"]
        )
        
        # Verify it
        context = await auth_service.verify_token(token.token)
        
        assert isinstance(context, AuthContext)
        assert context.user_id == "user123"
        assert context.permissions == ["read"]
        assert context.is_authenticated is True
        assert context.is_expired is False
    
    @pytest.mark.asyncio
    async def test_verify_expired_token(self, auth_service, mock_time_service):
        """Test verifying an expired token."""
        await auth_service.start()
        
        # Create token
        token = await auth_service.create_token(
            user_id="user123",
            permissions=["read"]
        )
        
        # Advance time past expiry
        future_time = mock_time_service.now() + timedelta(hours=25)
        mock_time_service.now.return_value = future_time
        
        # Verify should fail
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.verify_token(token.token)
        
        assert "expired" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_verify_invalid_token(self, auth_service):
        """Test verifying an invalid token."""
        await auth_service.start()
        
        # Try to verify garbage token
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.verify_token("invalid.token.here")
        
        assert "invalid" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_refresh_token(self, auth_service):
        """Test refreshing a token."""
        await auth_service.start()
        
        # Create initial token
        token = await auth_service.create_token(
            user_id="user123",
            permissions=["read"]
        )
        
        # Refresh it
        new_token = await auth_service.refresh_token(token.refresh_token)
        
        assert isinstance(new_token, AuthToken)
        assert new_token.user_id == "user123"
        assert new_token.permissions == ["read"]
        assert new_token.token != token.token  # Should be different
    
    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, auth_service):
        """Test refreshing with invalid refresh token."""
        await auth_service.start()
        
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.refresh_token("invalid-refresh-token")
        
        assert "invalid" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_revoke_token(self, auth_service):
        """Test revoking a token."""
        await auth_service.start()
        
        # Create token
        token = await auth_service.create_token(
            user_id="user123",
            permissions=["read"]
        )
        
        # Verify it works
        context = await auth_service.verify_token(token.token)
        assert context.is_authenticated is True
        
        # Revoke it
        await auth_service.revoke_token(token.token)
        
        # Verify should now fail
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.verify_token(token.token)
        
        assert "revoked" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_check_permission_allowed(self, auth_service):
        """Test checking permissions - allowed case."""
        await auth_service.start()
        
        # Create context with permissions
        context = AuthContext(
            user_id="user123",
            permissions=["read", "write"],
            is_authenticated=True,
            is_expired=False,
            token_type=TokenType.ACCESS
        )
        
        # Check allowed permission
        allowed = await auth_service.check_permission(context, "read")
        assert allowed is True
    
    @pytest.mark.asyncio
    async def test_check_permission_denied(self, auth_service):
        """Test checking permissions - denied case."""
        await auth_service.start()
        
        # Create context with limited permissions
        context = AuthContext(
            user_id="user123",
            permissions=["read"],
            is_authenticated=True,
            is_expired=False,
            token_type=TokenType.ACCESS
        )
        
        # Check denied permission
        allowed = await auth_service.check_permission(context, "admin")
        assert allowed is False
    
    @pytest.mark.asyncio
    async def test_check_permission_unauthenticated(self, auth_service):
        """Test checking permissions for unauthenticated context."""
        await auth_service.start()
        
        # Create unauthenticated context
        context = AuthContext(
            user_id=None,
            permissions=[],
            is_authenticated=False,
            is_expired=False,
            token_type=TokenType.ACCESS
        )
        
        # Should always be denied
        allowed = await auth_service.check_permission(context, "read")
        assert allowed is False
    
    @pytest.mark.asyncio
    async def test_validate_api_key(self, auth_service):
        """Test API key validation."""
        await auth_service.start()
        
        # Register an API key
        api_key = "test-api-key-123"
        await auth_service.register_api_key(
            api_key,
            user_id="api-user",
            permissions=["api.read", "api.write"]
        )
        
        # Validate it
        context = await auth_service.validate_api_key(api_key)
        
        assert context.is_authenticated is True
        assert context.user_id == "api-user"
        assert "api.read" in context.permissions
    
    @pytest.mark.asyncio
    async def test_validate_invalid_api_key(self, auth_service):
        """Test invalid API key validation."""
        await auth_service.start()
        
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.validate_api_key("invalid-key")
        
        assert "invalid" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_create_service_token(self, auth_service):
        """Test creating service-to-service token."""
        await auth_service.start()
        
        token = await auth_service.create_service_token(
            service_name="telemetry",
            target_service="memory",
            ttl_minutes=5
        )
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Verify it
        context = await auth_service.verify_token(token)
        assert context.token_type == TokenType.SERVICE
        assert context.metadata["service_name"] == "telemetry"
        assert context.metadata["target_service"] == "memory"
    
    @pytest.mark.asyncio
    async def test_permission_levels(self, auth_service):
        """Test permission level checks."""
        await auth_service.start()
        
        # Create admin context
        admin_context = AuthContext(
            user_id="admin",
            permissions=["admin"],
            permission_level=PermissionLevel.ADMIN,
            is_authenticated=True,
            is_expired=False,
            token_type=TokenType.ACCESS
        )
        
        # Admin should have access to everything
        assert await auth_service.check_permission(admin_context, "anything") is True
        
        # Create read-only context
        readonly_context = AuthContext(
            user_id="viewer",
            permissions=["read"],
            permission_level=PermissionLevel.READ_ONLY,
            is_authenticated=True,
            is_expired=False,
            token_type=TokenType.ACCESS
        )
        
        # Read-only should not have write access
        assert await auth_service.check_permission(readonly_context, "write") is False
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_tokens(self, auth_service, mock_time_service):
        """Test cleanup of expired tokens."""
        await auth_service.start()
        
        # Create some tokens
        token1 = await auth_service.create_token("user1", ["read"])
        token2 = await auth_service.create_token("user2", ["write"])
        
        # Advance time to expire token1
        future_time = mock_time_service.now() + timedelta(hours=25)
        mock_time_service.now.return_value = future_time
        
        # Create another token after time advance
        token3 = await auth_service.create_token("user3", ["admin"])
        
        # Run cleanup
        cleaned = await auth_service._cleanup_expired_tokens()
        
        # Should have cleaned some tokens
        assert cleaned > 0
        
        # Token3 should still be valid
        context = await auth_service.verify_token(token3.token)
        assert context.is_authenticated is True
    
    def test_get_capabilities(self, auth_service):
        """Test getting service capabilities."""
        caps = auth_service.get_capabilities()
        
        assert isinstance(caps, ServiceCapabilities)
        assert caps.service_name == "AuthenticationService"
        assert "create_token" in caps.actions
        assert "verify_token" in caps.actions
        assert "refresh_token" in caps.actions
        assert "check_permission" in caps.actions
    
    def test_get_status(self, auth_service):
        """Test getting service status."""
        auth_service._running = True
        auth_service._active_tokens["token1"] = Mock()
        auth_service._api_keys["key1"] = Mock()
        auth_service._revoked_tokens.add("revoked1")
        
        status = auth_service.get_status()
        
        assert isinstance(status, ServiceStatus)
        assert status.is_healthy is True
        assert status.metrics["active_tokens"] == 1.0
        assert status.metrics["api_keys"] == 1.0
        assert status.metrics["revoked_tokens"] == 1.0
    
    @pytest.mark.asyncio
    async def test_encrypt_token_metadata(self, auth_service, mock_secrets_service):
        """Test that sensitive metadata is encrypted."""
        await auth_service.start()
        
        sensitive_data = {"password": "secret123"}
        token = await auth_service.create_token(
            user_id="user123",
            permissions=["read"],
            metadata=sensitive_data
        )
        
        # Secrets service should have been called to encrypt
        mock_secrets_service.encrypt.assert_called()
        
        # Token should be created successfully
        assert token is not None
    
    @pytest.mark.asyncio
    async def test_concurrent_token_creation(self, auth_service):
        """Test concurrent token creation."""
        await auth_service.start()
        
        # Create multiple tokens concurrently
        tasks = []
        for i in range(10):
            task = auth_service.create_token(f"user{i}", ["read"])
            tasks.append(task)
        
        tokens = await asyncio.gather(*tasks)
        
        # All should succeed
        assert len(tokens) == 10
        assert all(isinstance(t, AuthToken) for t in tokens)
        
        # All tokens should be different
        token_values = [t.token for t in tokens]
        assert len(set(token_values)) == 10
    
    @pytest.mark.asyncio
    async def test_token_with_custom_expiry(self, auth_service):
        """Test creating token with custom expiry."""
        await auth_service.start()
        
        # Create token with 1 minute expiry
        token = await auth_service.create_token(
            user_id="user123",
            permissions=["read"],
            ttl_hours=1/60  # 1 minute
        )
        
        # Verify expiry is set correctly
        decoded = jwt.decode(
            token.token,
            options={"verify_signature": False}
        )
        
        exp_time = datetime.fromtimestamp(decoded['exp'], tz=timezone.utc)
        expected_exp = auth_service.time_service.now() + timedelta(minutes=1)
        
        # Should be close (within 1 second)
        assert abs((exp_time - expected_exp).total_seconds()) < 1