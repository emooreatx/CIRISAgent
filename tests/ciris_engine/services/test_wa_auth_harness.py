"""
Test harness for WA authentication - provides isolated test environment.

This module provides fixtures and utilities for testing WA authentication
without touching production keys or databases.
"""

import pytest
import tempfile
import shutil
import os
import sqlite3
import secrets
import base64
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.backends import default_backend

from ciris_engine.services.wa_auth_service import WAAuthService
from ciris_engine.schemas.wa_schemas_v1 import (
    WACertificate, WARole, TokenType, JWTSubType
)


class WATestHarness:
    """Test harness for WA authentication testing."""
    
    def __init__(self, temp_dir: Path):
        """Initialize test harness with isolated directories."""
        self.temp_dir = temp_dir
        self.ciris_dir = temp_dir / ".ciris"
        self.ciris_dir.mkdir(mode=0o700, exist_ok=True)
        
        # Key directories
        self.wa_keys_dir = self.ciris_dir / "wa_keys"
        self.wa_keys_dir.mkdir(mode=0o700, exist_ok=True)
        
        # Database path
        self.db_path = temp_dir / "test_wa.db"
        
        # Test keys storage
        self.test_keys: Dict[str, Tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]] = {}
        
        # Counter for unique IDs
        self._id_counter = 0
        
        # Initialize service
        self.service = WAAuthService(
            db_path=str(self.db_path),
            key_dir=str(self.ciris_dir)
        )
    
    def _generate_wa_id(self) -> str:
        """Generate a properly formatted wa_id for testing."""
        self._id_counter += 1
        date_part = utc_now().strftime("%Y-%m-%d")
        random_part = f"TEST{self._id_counter:02d}"  # TEST01, TEST02, etc.
        return f"wa-{date_part}-{random_part}"
    
    def generate_test_keypair(self, name: str = "test") -> Tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]:
        """Generate a test Ed25519 keypair."""
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        self.test_keys[name] = (private_key, public_key)
        return private_key, public_key
    
    def save_private_key(self, private_key: ed25519.Ed25519PrivateKey, filename: str) -> Path:
        """Save private key to test directory."""
        key_path = self.ciris_dir / filename
        
        # Serialize private key
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        key_path.write_bytes(private_bytes)
        key_path.chmod(0o600)
        return key_path
    
    async def create_test_root(self, name: str = "test_root") -> WACertificate:
        """Create a test root WA certificate."""
        # Generate keypair
        private_key, public_key = self.generate_test_keypair(name)
        
        # Save private key
        self.save_private_key(private_key, f"{name}.key")
        
        # Get public key bytes
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        # Create certificate
        cert = WACertificate(
            wa_id=self._generate_wa_id(),
            name=name,
            role=WARole.ROOT,
            pubkey=base64.urlsafe_b64encode(public_bytes).decode().rstrip('='),
            jwt_kid=f"wa-jwt-{name}",
            scopes_json='["*"]',
            created=utc_now_iso(),
            active=True,
            token_type=TokenType.STANDARD
        )
        
        # Insert into database
        await self.service.create_wa(cert)
        
        return cert
    
    async def create_test_authority(self, name: str, parent_wa_id: str) -> WACertificate:
        """Create a test authority WA certificate signed by parent."""
        # Generate keypair
        private_key, public_key = self.generate_test_keypair(name)
        
        # Save private key
        self.save_private_key(private_key, f"{name}.key")
        
        # Get public key bytes
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        # Create certificate
        cert = WACertificate(
            wa_id=self._generate_wa_id(),
            name=name,
            role=WARole.AUTHORITY,
            pubkey=base64.urlsafe_b64encode(public_bytes).decode().rstrip('='),
            jwt_kid=f"wa-jwt-{name}",
            scopes_json='["wa:approve", "write:task"]',
            parent_wa_id=parent_wa_id,
            created=utc_now_iso(),
            active=True,
            token_type=TokenType.STANDARD
        )
        
        # TODO: Add parent signature (would need parent private key)
        
        # Insert into database
        await self.service.create_wa(cert)
        
        return cert
    
    async def create_test_observer(self, channel_id: str) -> WACertificate:
        """Create a test observer certificate for a channel."""
        # Observers don't have their own keys
        # They use gateway.secret for JWT signing
        
        cert = WACertificate(
            wa_id=self._generate_wa_id(),
            name=f"Observer {channel_id}",
            role=WARole.OBSERVER,
            pubkey="observer-no-key",  # Observers don't have keys
            jwt_kid=f"wa-jwt-obs-{channel_id.replace(':', '-')}",
            scopes_json='["read:any", "write:message"]',
            adapter_id=channel_id,
            created=utc_now_iso(),
            active=True,
            token_type=TokenType.CHANNEL
        )
        
        # Insert into database
        await self.service.create_wa(cert)
        
        return cert
    
    def get_test_jwt(self, wa_id: str, sub_type: JWTSubType = JWTSubType.AUTHORITY) -> str:
        """Generate a test JWT for a WA."""
        wa = asyncio.run(self.service.get_wa(wa_id))
        if not wa:
            raise ValueError(f"WA {wa_id} not found")
        
        if sub_type == JWTSubType.AUTHORITY and wa.role in [WARole.ROOT, WARole.AUTHORITY]:
            # Sign with WA's private key
            private_key = self.test_keys.get(wa.name)
            if not private_key:
                raise ValueError(f"No private key found for {wa.name}")
            
            return asyncio.run(self.service.issue_authority_token(wa_id))
        else:
            # Sign with gateway secret
            return asyncio.run(self.service.issue_user_token(
                wa_id=wa_id,
                password=None  # Skip password check for tests
            ))
    
    def cleanup(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)


@pytest.fixture(scope="function")
def wa_test_harness(tmp_path):
    """Provide a WA test harness for each test."""
    harness = WATestHarness(tmp_path)
    yield harness
    # Cleanup is automatic with tmp_path


@pytest.fixture(scope="function") 
def wa_test_env(tmp_path, monkeypatch):
    """Set up isolated WA test environment."""
    # Create test directories
    test_ciris_dir = tmp_path / ".ciris"
    test_ciris_dir.mkdir(mode=0o700, exist_ok=True)
    
    # Override home directory for tests
    monkeypatch.setenv("HOME", str(tmp_path))
    
    # Create test database
    test_db = tmp_path / "test_wa.db"
    
    return {
        "home": tmp_path,
        "ciris_dir": test_ciris_dir,
        "db_path": test_db,
        "service": WAAuthService(str(test_db), str(test_ciris_dir))
    }


@pytest.fixture(scope="function")
def wa_test_keys(wa_test_env):
    """Generate test Ed25519 keypairs."""
    import asyncio
    from cryptography.hazmat.primitives.asymmetric import ed25519
    
    keys = {}
    
    # Generate root keypair
    root_private = ed25519.Ed25519PrivateKey.generate()
    root_public = root_private.public_key()
    keys["root"] = (root_private, root_public)
    
    # Generate authority keypair
    auth_private = ed25519.Ed25519PrivateKey.generate()
    auth_public = auth_private.public_key()
    keys["authority"] = (auth_private, auth_public)
    
    # Save keys to test directory
    ciris_dir = wa_test_env["ciris_dir"]
    
    # Save root private key
    root_key_path = ciris_dir / "test_root.key"
    root_key_path.write_bytes(
        root_private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
    )
    root_key_path.chmod(0o600)
    
    # Save authority private key
    auth_key_path = ciris_dir / "test_authority.key"
    auth_key_path.write_bytes(
        auth_private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
    )
    auth_key_path.chmod(0o600)
    
    # Also save at the location SDK tests expect
    wa_key_path = ciris_dir / "wa_private_key.pem"
    wa_key_path.write_bytes(
        auth_private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
    )
    wa_key_path.chmod(0o600)
    
    return keys


# Make asyncio.run available for the harness
import asyncio
from ciris_engine.utils.time_utils import utc_now_iso, utc_now