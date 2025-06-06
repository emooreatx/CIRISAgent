"""Tests for secrets storage system."""
import pytest
import tempfile
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from ciris_engine.secrets.store import (
    SecretsStore, 
    SecretsEncryption, 
    SecretRecord,
    SecretAccessLog
)


class TestSecretsEncryption:
    """Test encryption/decryption functionality."""
    
    def test_encryption_roundtrip(self):
        """Test basic encryption and decryption."""
        encryption = SecretsEncryption()
        
        original_secret = "my_secret_api_key_12345"
        encrypted_value, salt, nonce = encryption.encrypt_secret(original_secret)
        
        # Should be different from original
        assert encrypted_value != original_secret.encode()
        assert len(salt) == 16
        assert len(nonce) == 12
        
        # Should decrypt back to original
        decrypted_secret = encryption.decrypt_secret(encrypted_value, salt, nonce)
        assert decrypted_secret == original_secret
        
    def test_different_encryptions_different_results(self):
        """Test that same value encrypts differently each time."""
        encryption = SecretsEncryption()
        
        secret = "same_secret_value"
        encrypted1, salt1, nonce1 = encryption.encrypt_secret(secret)
        encrypted2, salt2, nonce2 = encryption.encrypt_secret(secret)
        
        # Should be different due to random salt/nonce
        assert encrypted1 != encrypted2
        assert salt1 != salt2
        assert nonce1 != nonce2
        
        # But both should decrypt to same value
        decrypted1 = encryption.decrypt_secret(encrypted1, salt1, nonce1)
        decrypted2 = encryption.decrypt_secret(encrypted2, salt2, nonce2)
        assert decrypted1 == decrypted2 == secret
        
    def test_master_key_provided(self):
        """Test encryption with provided master key."""
        master_key = b"a" * 32  # 32-byte key
        encryption = SecretsEncryption(master_key)
        
        assert encryption.master_key == master_key
        
        # Should work normally
        secret = "test_secret"
        encrypted, salt, nonce = encryption.encrypt_secret(secret)
        decrypted = encryption.decrypt_secret(encrypted, salt, nonce)
        assert decrypted == secret
        
    def test_invalid_master_key_length(self):
        """Test that invalid master key length raises error."""
        with pytest.raises(ValueError, match="Master key must be 32 bytes"):
            SecretsEncryption(b"too_short")
            
    def test_key_rotation(self):
        """Test master key rotation."""
        encryption = SecretsEncryption()
        old_key = encryption.master_key
        
        new_key = encryption.rotate_master_key()
        assert new_key != old_key
        assert encryption.master_key == new_key
        
        # Should work with new key
        secret = "test_after_rotation"
        encrypted, salt, nonce = encryption.encrypt_secret(secret)
        decrypted = encryption.decrypt_secret(encrypted, salt, nonce)
        assert decrypted == secret
        
    def test_unicode_secrets(self):
        """Test encryption of unicode strings."""
        encryption = SecretsEncryption()
        
        unicode_secret = "🔐 Secret with émojis and açcénts 🗝️"
        encrypted, salt, nonce = encryption.encrypt_secret(unicode_secret)
        decrypted = encryption.decrypt_secret(encrypted, salt, nonce)
        
        assert decrypted == unicode_secret


class TestSecretsStore:
    """Test secrets storage functionality."""
    
    @pytest.fixture
    def temp_store(self):
        """Create temporary secrets store."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_secrets.db"
            store = SecretsStore(str(db_path))
            yield store
            
    @pytest.fixture
    def sample_secret_record(self):
        """Create sample secret record."""
        return SecretRecord(
            secret_uuid="test-uuid-1234",
            encrypted_value=b"",  # Will be set by store
            encryption_key_ref="",  # Will be set by store
            salt=b"",  # Will be set by store
            nonce=b"",  # Will be set by store
            description="Test API Key",
            sensitivity_level="HIGH",
            detected_pattern="api_key",
            context_hint="test context",
            created_at=datetime.now(),
            auto_decapsulate_for_actions=["tool"],
            manual_access_only=False
        )
        
    @pytest.mark.asyncio
    async def test_store_and_retrieve_secret(self, temp_store, sample_secret_record):
        """Test basic store and retrieve functionality."""
        original_value = "secret_api_key_12345"
        
        # Store secret
        stored = await temp_store.store_secret(sample_secret_record, original_value)
        assert stored
        
        # Retrieve secret
        retrieved = await temp_store.retrieve_secret(
            sample_secret_record.secret_uuid,
            "test retrieval",
            "test_user"
        )
        
        assert retrieved is not None
        assert retrieved.secret_uuid == sample_secret_record.secret_uuid
        assert retrieved.description == sample_secret_record.description
        assert retrieved.sensitivity_level == sample_secret_record.sensitivity_level
        assert retrieved.access_count == 1
        
        # Decrypt and verify
        decrypted = await temp_store.decrypt_secret_value(retrieved)
        assert decrypted == original_value
        
    @pytest.mark.asyncio
    async def test_secret_not_found(self, temp_store):
        """Test retrieval of non-existent secret."""
        retrieved = await temp_store.retrieve_secret(
            "non-existent-uuid",
            "test purpose",
            "test_user"
        )
        assert retrieved is None
        
    @pytest.mark.asyncio
    async def test_access_count_tracking(self, temp_store, sample_secret_record):
        """Test that access count is properly tracked."""
        original_value = "test_secret"
        
        # Store secret
        await temp_store.store_secret(sample_secret_record, original_value)
        
        # Access multiple times
        for i in range(3):
            retrieved = await temp_store.retrieve_secret(
                sample_secret_record.secret_uuid,
                f"access {i}",
                "test_user"
            )
            assert retrieved.access_count == i + 1
            
    @pytest.mark.asyncio
    async def test_last_accessed_tracking(self, temp_store, sample_secret_record):
        """Test that last accessed time is tracked."""
        original_value = "test_secret"
        
        # Store secret
        await temp_store.store_secret(sample_secret_record, original_value)
        
        # First access
        before_access = datetime.now()
        retrieved = await temp_store.retrieve_secret(
            sample_secret_record.secret_uuid,
            "first access",
            "test_user"
        )
        after_access = datetime.now()
        
        assert retrieved.last_accessed is not None
        assert before_access <= retrieved.last_accessed <= after_access
        
    @pytest.mark.asyncio
    async def test_delete_secret(self, temp_store, sample_secret_record):
        """Test secret deletion."""
        original_value = "test_secret"
        
        # Store secret
        await temp_store.store_secret(sample_secret_record, original_value)
        
        # Verify it exists
        retrieved = await temp_store.retrieve_secret(
            sample_secret_record.secret_uuid,
            "verify exists",
            "test_user"
        )
        assert retrieved is not None
        
        # Delete secret
        deleted = await temp_store.delete_secret(
            sample_secret_record.secret_uuid,
            "test_user"
        )
        assert deleted
        
        # Should no longer exist
        retrieved = await temp_store.retrieve_secret(
            sample_secret_record.secret_uuid,
            "verify deleted",
            "test_user"
        )
        assert retrieved is None
        
    @pytest.mark.asyncio
    async def test_list_secrets(self, temp_store):
        """Test listing stored secrets."""
        # Store multiple secrets
        secrets_data = [
            ("uuid1", "API Key", "HIGH", "api_key", "secret1"),
            ("uuid2", "Password", "CRITICAL", "password", "secret2"),
            ("uuid3", "Token", "HIGH", "bearer_token", "secret3")
        ]
        
        for uuid, desc, sensitivity, pattern, value in secrets_data:
            record = SecretRecord(
                secret_uuid=uuid,
                encrypted_value=b"",
                encryption_key_ref="",
                salt=b"",
                nonce=b"",
                description=desc,
                sensitivity_level=sensitivity,
                detected_pattern=pattern,
                context_hint="test",
                created_at=datetime.now()
            )
            await temp_store.store_secret(record, value)
            
        # List all secrets
        all_secrets = await temp_store.list_secrets()
        assert len(all_secrets) == 3
        
        # List by pattern
        api_secrets = await temp_store.list_secrets(pattern_filter="api_key")
        assert len(api_secrets) == 1
        assert api_secrets[0].description == "API Key"
        
        # List by sensitivity
        high_secrets = await temp_store.list_secrets(sensitivity_filter="HIGH")
        assert len(high_secrets) == 2
        
    @pytest.mark.asyncio
    async def test_rate_limiting(self, temp_store, sample_secret_record):
        """Test rate limiting functionality."""
        # Use very low limits for testing
        temp_store.max_accesses_per_minute = 2
        temp_store.max_accesses_per_hour = 5
        
        original_value = "test_secret"
        await temp_store.store_secret(sample_secret_record, original_value)
        
        # Should work for first few accesses
        for i in range(2):
            retrieved = await temp_store.retrieve_secret(
                sample_secret_record.secret_uuid,
                f"access {i}",
                "test_user"
            )
            assert retrieved is not None
            
        # Should be rate limited now
        retrieved = await temp_store.retrieve_secret(
            sample_secret_record.secret_uuid,
            "rate limited access",
            "test_user"
        )
        assert retrieved is None
        
    @pytest.mark.asyncio
    async def test_different_users_separate_limits(self, temp_store, sample_secret_record):
        """Test that different users have separate rate limits."""
        temp_store.max_accesses_per_minute = 1
        
        original_value = "test_secret"
        await temp_store.store_secret(sample_secret_record, original_value)
        
        # User1 accesses (should work)
        retrieved = await temp_store.retrieve_secret(
            sample_secret_record.secret_uuid,
            "user1 access",
            "user1"
        )
        assert retrieved is not None
        
        # User2 accesses (should still work - separate limit)
        retrieved = await temp_store.retrieve_secret(
            sample_secret_record.secret_uuid,
            "user2 access",
            "user2"
        )
        assert retrieved is not None
        
        # User1 accesses again (should be rate limited)
        retrieved = await temp_store.retrieve_secret(
            sample_secret_record.secret_uuid,
            "user1 second access",
            "user1"
        )
        assert retrieved is None
        
    @pytest.mark.asyncio
    async def test_secret_replacement_in_store(self, temp_store):
        """Test that storing with same UUID replaces existing secret."""
        # Create first secret
        record1 = SecretRecord(
            secret_uuid="same-uuid",
            encrypted_value=b"",
            encryption_key_ref="",
            salt=b"",
            nonce=b"",
            description="First Secret",
            sensitivity_level="HIGH",
            detected_pattern="api_key",
            context_hint="first",
            created_at=datetime.now()
        )
        await temp_store.store_secret(record1, "first_value")
        
        # Create second secret with same UUID
        record2 = SecretRecord(
            secret_uuid="same-uuid",
            encrypted_value=b"",
            encryption_key_ref="",
            salt=b"",
            nonce=b"",
            description="Second Secret",
            sensitivity_level="CRITICAL",
            detected_pattern="password",
            context_hint="second",
            created_at=datetime.now()
        )
        await temp_store.store_secret(record2, "second_value")
        
        # Should only have one secret
        all_secrets = await temp_store.list_secrets()
        assert len(all_secrets) == 1
        
        # Should be the second secret
        retrieved = await temp_store.retrieve_secret("same-uuid", "test", "user")
        assert retrieved.description == "Second Secret"
        assert retrieved.sensitivity_level == "CRITICAL"
        
        decrypted = await temp_store.decrypt_secret_value(retrieved)
        assert decrypted == "second_value"
        
    @pytest.mark.asyncio
    async def test_concurrent_access(self, temp_store, sample_secret_record):
        """Test concurrent access to secrets store."""
        original_value = "concurrent_test_secret"
        await temp_store.store_secret(sample_secret_record, original_value)
        
        # Create multiple concurrent retrieval tasks
        async def retrieve_secret(user_id):
            return await temp_store.retrieve_secret(
                sample_secret_record.secret_uuid,
                f"concurrent access {user_id}",
                f"user_{user_id}"
            )
            
        # Run 5 concurrent retrievals
        tasks = [retrieve_secret(i) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        # All should succeed (different users)
        for result in results:
            assert result is not None
            assert result.secret_uuid == sample_secret_record.secret_uuid
            
        # Check final access count
        final_retrieved = await temp_store.retrieve_secret(
            sample_secret_record.secret_uuid,
            "final check",
            "final_user"
        )
        # Should be 6 total (5 concurrent + 1 final)
        assert final_retrieved.access_count == 6