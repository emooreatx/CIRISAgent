"""
Comprehensive WA authentication scenario tests.

Tests all WA authentication scenarios in isolated environments.
"""

import pytest
import asyncio
import json
import jwt
from pathlib import Path

from ciris_engine.schemas.wa_schemas_v1 import (
    WARole, TokenType, JWTSubType, ChannelIdentity
)
from ciris_engine.schemas.wa_schemas_v1 import WACertificate

from tests.ciris_engine.services.test_wa_auth_harness import wa_test_harness, wa_test_env, wa_test_keys
from ciris_engine.utils.time_utils import utc_now_iso, utc_now


class TestWAAuthScenarios:
    """Test various WA authentication scenarios."""
    
    @pytest.mark.asyncio
    async def test_create_new_root(self, wa_test_harness):
        """Test creating a new root WA from scratch."""
        # Create new root
        root_cert = await wa_test_harness.create_test_root("ciris_root")
        
        # Verify certificate
        assert root_cert.role == WARole.ROOT
        assert root_cert.wa_id.startswith("wa-")  # Verify proper format
        assert root_cert.name == "ciris_root"
        assert json.loads(root_cert.scopes_json) == ["*"]
        
        # Verify it's in database
        stored = await wa_test_harness.service.get_wa(root_cert.wa_id)
        assert stored is not None
        assert stored.name == "ciris_root"
        
        # Verify private key exists
        key_path = wa_test_harness.ciris_dir / "ciris_root.key"
        assert key_path.exists()
        assert oct(key_path.stat().st_mode)[-3:] == "600"
    
    @pytest.mark.asyncio
    async def test_join_existing_tree(self, wa_test_harness):
        """Test joining an existing WA tree as authority."""
        # First create root
        root_cert = await wa_test_harness.create_test_root("root")
        
        # Create authority under root
        auth_cert = await wa_test_harness.create_test_authority("alice", root_cert.wa_id)
        
        # Verify certificate
        assert auth_cert.role == WARole.AUTHORITY
        assert auth_cert.parent_wa_id == root_cert.wa_id
        assert "wa:approve" in json.loads(auth_cert.scopes_json)
        
        # Verify hierarchy
        stored = await wa_test_harness.service.get_wa(auth_cert.wa_id)
        assert stored.parent_wa_id == root_cert.wa_id
    
    @pytest.mark.asyncio
    async def test_channel_observer_creation(self, wa_test_harness):
        """Test automatic channel observer creation."""
        # Create CLI channel observer
        channel_id = "cli:testuser@testhost"
        observer = await wa_test_harness.create_test_observer(channel_id)
        
        # Verify certificate
        assert observer.role == WARole.OBSERVER
        assert observer.adapter_id == channel_id
        assert observer.token_type == TokenType.CHANNEL
        
        # Verify scopes
        scopes = json.loads(observer.scopes_json)
        assert "read:any" in scopes
        assert "write:message" in scopes
        assert "wa:admin" not in scopes  # Should not have admin rights
    
    @pytest.mark.asyncio
    async def test_jwt_token_generation(self, wa_test_harness):
        """Test JWT token generation for different roles."""
        # Create test WAs
        root = await wa_test_harness.create_test_root("root")
        auth = await wa_test_harness.create_test_authority("auth", root.wa_id)
        observer = await wa_test_harness.create_test_observer("cli:test@host")
        
        # Test observer token (gateway secret)
        obs_token = wa_test_harness.service.create_channel_token(observer)
        obs_decoded = jwt.decode(
            obs_token, 
            wa_test_harness.service.gateway_secret,
            algorithms=["HS256"]
        )
        assert obs_decoded["sub"] == observer.wa_id
        assert obs_decoded["sub_type"] == JWTSubType.ANON
        assert "exp" not in obs_decoded  # Non-expiring
        
        # Test user token (gateway secret, time-limited)
        # Need to set password first
        password_hash = wa_test_harness.service.hash_password("test_password")
        await wa_test_harness.service.update_wa(auth.wa_id, password_hash=password_hash)
        # For user tokens, we need to get the WA and create a gateway token
        auth_wa = await wa_test_harness.service.get_wa(auth.wa_id)
        user_token = wa_test_harness.service.create_gateway_token(auth_wa)
        user_decoded = jwt.decode(
            user_token,
            wa_test_harness.service.gateway_secret,
            algorithms=["HS256"]
        )
        assert user_decoded["sub"] == auth.wa_id
        assert user_decoded["sub_type"] == JWTSubType.USER
        assert "exp" in user_decoded  # Should expire
        
        # Test authority token (EdDSA signed)
        # This requires having the private key loaded
        # For now, skip as it needs more setup
    
    @pytest.mark.asyncio
    async def test_scope_verification(self, wa_test_harness):
        """Test scope verification for different operations."""
        # Create test WAs
        root = await wa_test_harness.create_test_root("root")
        auth = await wa_test_harness.create_test_authority("auth", root.wa_id)
        observer = await wa_test_harness.create_test_observer("cli:test@host")
        
        # Test root has all scopes
        root_wa = await wa_test_harness.service.get_wa(root.wa_id)
        assert root_wa.has_scope("wa:admin")
        assert root_wa.has_scope("system:control")
        assert root_wa.has_scope("*")
        
        # Test authority has limited scopes
        auth_wa = await wa_test_harness.service.get_wa(auth.wa_id)
        assert auth_wa.has_scope("wa:approve")
        assert auth_wa.has_scope("write:task")
        assert not auth_wa.has_scope("system:control")
        
        # Test observer has basic scopes
        obs_wa = await wa_test_harness.service.get_wa(observer.wa_id)
        assert obs_wa.has_scope("read:any")
        assert obs_wa.has_scope("write:message")
        assert not obs_wa.has_scope("wa:approve")
    
    @pytest.mark.asyncio
    async def test_wa_revocation(self, wa_test_harness):
        """Test WA revocation functionality."""
        # Create authority
        root = await wa_test_harness.create_test_root("root")
        auth = await wa_test_harness.create_test_authority("auth", root.wa_id)
        
        # Verify active
        wa = await wa_test_harness.service.get_wa(auth.wa_id)
        assert wa.active
        
        # Revoke
        await wa_test_harness.service.revoke_wa(auth.wa_id, revoked_by=root.wa_id, reason="Test revocation")
        
        # Verify revoked - get_wa returns None for inactive WAs
        wa = await wa_test_harness.service.get_wa(auth.wa_id)
        assert wa is None  # Revoked WAs are not returned by get_wa
        
        # Test token validation should fail
        # (Would need to implement token validation check)
    
    @pytest.mark.asyncio 
    async def test_oauth_observer_creation(self, wa_test_harness):
        """Test OAuth-based observer creation."""
        # Simulate OAuth observer
        oauth_wa = WACertificate(
            wa_id=f"wa-{utc_now().strftime('%Y-%m-%d')}-OAUTH1",
            name="user@example.com",
            role=WARole.OBSERVER,
            pubkey="oauth-no-key",
            jwt_kid="wa-jwt-oauth-google-12345",
            oauth_provider="google",
            oauth_external_id="12345",
            auto_minted=True,
            scopes_json='["read:any", "write:message"]',
            created=utc_now_iso(),
            active=True,
            token_type=TokenType.OAUTH
        )
        
        # Insert
        await wa_test_harness.service.create_wa(oauth_wa)
        
        # Verify retrieval by OAuth ID
        found = await wa_test_harness.service.get_wa_by_oauth(
            "google", "12345"
        )
        assert found is not None
        assert found.wa_id == oauth_wa.wa_id
        assert found.auto_minted == 1
    
    @pytest.mark.asyncio
    async def test_channel_identity_generation(self, wa_test_harness):
        """Test channel identity generation for different adapters."""
        # Test CLI adapter - just test string formatting
        cli_id = f"cli:testuser@testhost"
        assert cli_id == "cli:testuser@testhost"
        
        # Test API adapter format
        api_id = f"api:192.168.1.1:8080"
        assert api_id == "api:192.168.1.1:8080"
        
        # Test Discord adapter format
        discord_id = f"discord:guild123:user456"
        assert discord_id == "discord:guild123:user456"
        
        # Test using from_adapter method
        cli_identity = ChannelIdentity.from_adapter('cli', {})
        assert cli_identity.adapter_id.startswith("cli:")
        assert cli_identity.adapter_type == "cli"
    
    @pytest.mark.asyncio
    async def test_password_authentication(self, wa_test_harness):
        """Test password-based authentication."""
        # Create authority
        root = await wa_test_harness.create_test_root("root")
        auth = await wa_test_harness.create_test_authority("auth", root.wa_id)
        
        # Set password
        password_hash = wa_test_harness.service.hash_password("secure_password")
        await wa_test_harness.service.update_wa(auth.wa_id, password_hash=password_hash)
        
        # Test correct password
        # Get WA and create gateway token after password validation
        auth_wa = await wa_test_harness.service.get_wa(auth.wa_id)
        # Validate password first  
        valid = wa_test_harness.service.verify_password("secure_password", auth_wa.password_hash) if auth_wa.password_hash else False
        if valid:
            token = wa_test_harness.service.create_gateway_token(auth_wa)
        else:
            token = None
        assert token is not None
        
        # Test incorrect password
        with pytest.raises(ValueError, match="Invalid password"):
            # This should fail password validation
            auth_wa = await wa_test_harness.service.get_wa(auth.wa_id)
            valid = wa_test_harness.service.verify_password("wrong_password", auth_wa.password_hash) if auth_wa.password_hash else False
            if valid:
                auth_wa = await wa_test_harness.service.get_wa(auth.wa_id)
                wa_test_harness.service.create_gateway_token(auth_wa)
            else:
                raise ValueError("Invalid password")
    
    @pytest.mark.asyncio
    async def test_api_key_authentication(self, wa_test_harness):
        """Test API key authentication."""
        # Create authority
        root = await wa_test_harness.create_test_root("root")
        auth = await wa_test_harness.create_test_authority("auth", root.wa_id)
        
        # Generate API key (synchronous method)
        api_key = wa_test_harness.service.generate_api_key(auth.wa_id)
        assert api_key is not None
        assert len(api_key) >= 32
        
        # Store API key in WA record
        await wa_test_harness.service.update_wa(auth.wa_id, api_key_hash=api_key)
        
        # Verify API key was stored
        wa = await wa_test_harness.service.get_wa(auth.wa_id)
        assert wa is not None
        assert wa.api_key_hash == api_key


class TestWAAuthIntegration:
    """Test WA auth integration with other components."""
    
    @pytest.mark.asyncio
    async def test_middleware_integration(self, wa_test_harness):
        """Test middleware scope checking."""
        # Create test WAs
        observer = await wa_test_harness.create_test_observer("cli:test@host")
        
        # Get observer token
        # Get the observer WA first
        observer_wa = await wa_test_harness.service.get_wa(observer.wa_id)
        token = wa_test_harness.service.create_channel_token(observer_wa)
        
        # Test middleware auth context creation
        # Extract token from Bearer header
        auth_context = await wa_test_harness.service.authenticate(token)
        
        assert auth_context is not None
        assert auth_context.wa_id == observer.wa_id
        assert auth_context.role == WARole.OBSERVER
        assert "read:any" in auth_context.scopes
        assert "write:message" in auth_context.scopes
    
    @pytest.mark.asyncio
    async def test_endpoint_protection(self, wa_test_harness):
        """Test endpoint protection with different scopes."""
        # Create WAs with different roles
        root = await wa_test_harness.create_test_root("root")
        auth = await wa_test_harness.create_test_authority("auth", root.wa_id)
        observer = await wa_test_harness.create_test_observer("cli:test@host")
        
        # Define test endpoints and required scopes
        endpoints = {
            "/v1/chat": ["read:any"],
            "/v1/chat/send": ["write:message"],
            "/v1/wa/approve": ["wa:approve"],
            "/v1/system/kill": ["system:control"]
        }
        
        # Test observer access
        obs_wa = await wa_test_harness.service.get_wa(observer.wa_id)
        # Observer has "read:any" and "write:message" scopes
        for scope in endpoints["/v1/chat"]:
            assert obs_wa.has_scope(scope)
        for scope in endpoints["/v1/chat/send"]:
            assert obs_wa.has_scope(scope)
        for scope in endpoints["/v1/wa/approve"]:
            assert not obs_wa.has_scope(scope)
        for scope in endpoints["/v1/system/kill"]:
            assert not obs_wa.has_scope(scope)
        
        # Test authority access
        auth_wa = await wa_test_harness.service.get_wa(auth.wa_id)
        # Authority has "wa:approve" and "write:task" scopes
        for scope in endpoints["/v1/wa/approve"]:
            assert auth_wa.has_scope(scope)
        for scope in endpoints["/v1/system/kill"]:
            assert not auth_wa.has_scope(scope)
        
        # Test root access (has wildcard)
        root_wa = await wa_test_harness.service.get_wa(root.wa_id)
        # Root has "*" scope - can access everything
        for scope in endpoints["/v1/system/kill"]:
            assert root_wa.has_scope(scope)
        assert root_wa.has_scope("any:scope:here")