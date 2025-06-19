"""Tests for WA Authentication Service."""

import pytest
import tempfile
import os
from pathlib import Path
from datetime import datetime

from ciris_engine.services.wa_auth_service import WAAuthService
from ciris_engine.schemas.wa_schemas_v1 import WACertificate, WARole, TokenType


@pytest.fixture
async def auth_service():
    """Create a temporary auth service for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_wa.db")
        key_dir = os.path.join(tmpdir, "keys")
        
        service = WAAuthService(db_path, key_dir)
        await service.bootstrap_if_needed()
        
        yield service


@pytest.mark.asyncio
async def test_bootstrap_creates_root_wa(auth_service):
    """Test that bootstrap creates root WA from seed file."""
    # List all WAs
    was = await auth_service.list_all_was()
    
    # Should have one root WA
    assert len(was) == 1
    assert was[0].name == "ciris_root"
    assert was[0].role == WARole.ROOT
    assert was[0].wa_id == "wa-2025-06-14-ROOT00"


@pytest.mark.asyncio
async def test_create_channel_observer(auth_service):
    """Test creating an adapter observer WA."""
    adapter_id = "cli:testuser@testhost"
    name = "test_cli_observer"
    
    # Create adapter observer
    observer = await auth_service.create_adapter_observer(adapter_id, name)
    
    assert observer.role == WARole.OBSERVER
    assert observer.adapter_id == adapter_id
    assert observer.token_type == TokenType.CHANNEL
    assert observer.name == name
    
    # Verify it was stored
    fetched = await auth_service.get_wa_by_adapter(adapter_id)
    assert fetched is not None
    assert fetched.wa_id == observer.wa_id


@pytest.mark.asyncio
async def test_jwt_token_creation_and_validation(auth_service):
    """Test JWT token creation and validation."""
    # Create a test WA
    adapter_id = "test:adapter"
    observer = await auth_service.create_adapter_observer(adapter_id, "test_observer")
    
    # Create channel token
    token = auth_service.create_channel_token(observer)
    assert token is not None
    
    # Verify token
    auth_context = await auth_service.verify_token(token)
    assert auth_context is not None
    assert auth_context.wa_id == observer.wa_id
    # Note: auth_context doesn't have adapter_id field
    assert "read:any" in auth_context.scopes


@pytest.mark.asyncio
async def test_password_hashing(auth_service):
    """Test password hashing and verification."""
    password = "test_password_123"
    
    # Hash password
    hashed = auth_service.hash_password(password)
    assert hashed != password
    
    # Verify correct password
    assert auth_service.verify_password(password, hashed) is True
    
    # Verify wrong password
    assert auth_service.verify_password("wrong_password", hashed) is False


@pytest.mark.asyncio
async def test_keypair_generation(auth_service):
    """Test Ed25519 keypair generation."""
    private_key, public_key = auth_service.generate_keypair()
    
    assert len(private_key) == 32  # Ed25519 private key is 32 bytes
    assert len(public_key) == 32   # Ed25519 public key is 32 bytes
    
    # Test encoding/decoding
    encoded = auth_service._encode_public_key(public_key)
    decoded = auth_service._decode_public_key(encoded)
    
    assert decoded == public_key


@pytest.mark.asyncio
async def test_signature_operations(auth_service):
    """Test signing and verification."""
    private_key, public_key = auth_service.generate_keypair()
    data = b"test data to sign"
    
    # Sign data
    signature = auth_service.sign_data(data, private_key)
    
    # Verify with correct key
    pubkey_str = auth_service._encode_public_key(public_key)
    assert auth_service.verify_signature(data, signature, pubkey_str) is True
    
    # Verify with wrong data
    assert auth_service.verify_signature(b"wrong data", signature, pubkey_str) is False


@pytest.mark.asyncio
async def test_wa_id_generation(auth_service):
    """Test WA ID generation."""
    timestamp = datetime(2025, 6, 14, 12, 0, 0)
    
    wa_id = auth_service.generate_wa_id(timestamp)
    
    # Check format
    assert wa_id.startswith("wa-2025-06-14-")
    # The actual format is wa-YYYY-MM-DD-XXXXXX where XXXXXX is 6 uppercase hex chars
    # This gives us: wa- (3) + YYYY-MM-DD (10) + - (1) + XXXXXX (6) = 20 chars
    assert len(wa_id) == 20, f"Expected 20 chars, got {len(wa_id)} for {wa_id}"
    
    # Last 6 chars should be uppercase hex
    suffix = wa_id[-6:]
    # Check that all characters are valid hex digits
    assert all(c in "0123456789ABCDEF" for c in suffix)
    # Only check uppercase if there are actual letters (not just digits)
    if any(c in "ABCDEF" for c in suffix):
        assert suffix.isupper()