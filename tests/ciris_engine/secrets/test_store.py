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
from ciris_engine.schemas.secrets_schemas_v1 import DetectedSecret, SensitivityLevel


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
    def sample_detected_secret(self):
        """Create sample detected secret."""
        return DetectedSecret(
            secret_uuid="test-uuid-1234",
            original_value="secret_api_key_12345",
            replacement_text="{SECRET:test-uuid-1234:Test API Key}",
            pattern_name="api_keys",
            description="Test API Key",
            sensitivity=SensitivityLevel.HIGH,
            context_hint="test context"
        )
        
    @pytest.mark.asyncio
    async def test_store_and_retrieve_secret(self, temp_store, sample_detected_secret):
        """Test basic store and retrieve functionality."""
        
        # Store secret
        stored = await temp_store.store_secret(sample_detected_secret)
        assert stored
        
        # Retrieve secret
        retrieved = await temp_store.retrieve_secret(
            sample_detected_secret.secret_uuid,
            decrypt=False
        )
        
        assert retrieved is not None
        assert retrieved.secret_uuid == sample_detected_secret.secret_uuid
        assert retrieved.description == sample_detected_secret.description
        assert retrieved.sensitivity_level == sample_detected_secret.sensitivity
        assert retrieved.access_count == 1
        
        # Decrypt and verify
        decrypted = await temp_store.decrypt_secret_value(retrieved)
        assert decrypted == sample_detected_secret.original_value
        
    @pytest.mark.asyncio
    async def test_secret_not_found(self, temp_store):
        """Test retrieval of non-existent secret."""
        retrieved = await temp_store.retrieve_secret("non-existent-uuid")
        assert retrieved is None
        
    @pytest.mark.asyncio
    async def test_access_count_tracking(self, temp_store, sample_detected_secret):
        """Test that access count is properly tracked."""
        original_value = "test_secret"
        
        # Store secret
        await temp_store.store_secret(sample_detected_secret)
        
        # Access multiple times
        for i in range(3):
            retrieved = await temp_store.retrieve_secret(sample_detected_secret.secret_uuid)
            assert retrieved.access_count == i + 1
            
    @pytest.mark.asyncio
    async def test_last_accessed_tracking(self, temp_store, sample_detected_secret):
        """Test that last accessed time is tracked."""
        original_value = "test_secret"
        
        # Store secret
        await temp_store.store_secret(sample_detected_secret)
        
        # First access
        before_access = datetime.now()
        retrieved = await temp_store.retrieve_secret(
            sample_detected_secret.secret_uuid
        )
        after_access = datetime.now()
        
        assert retrieved.last_accessed is not None
        assert before_access <= retrieved.last_accessed <= after_access
        
    @pytest.mark.asyncio
    async def test_delete_secret(self, temp_store, sample_detected_secret):
        """Test secret deletion."""
        original_value = "test_secret"
        
        # Store secret
        await temp_store.store_secret(sample_detected_secret)
        
        # Verify it exists
        retrieved = await temp_store.retrieve_secret(sample_detected_secret.secret_uuid)
        assert retrieved is not None
        
        # Delete secret
        deleted = await temp_store.delete_secret(sample_detected_secret.secret_uuid)
        assert deleted
        
        # Should no longer exist
        retrieved = await temp_store.retrieve_secret(sample_detected_secret.secret_uuid)
        assert retrieved is None
        
    @pytest.mark.asyncio
    async def test_list_secrets(self, temp_store):
        """Test listing stored secrets."""
        # Store multiple secrets
        secrets_data = [
            ("uuid1", "API Key", "HIGH", "api_keys", "secret1"),
            ("uuid2", "Password", "CRITICAL", "passwords", "secret2"),
            ("uuid3", "Token", "HIGH", "bearer_tokens", "secret3")
        ]
        
        for uuid, desc, sensitivity, pattern, value in secrets_data:
            from ciris_engine.schemas.secrets_schemas_v1 import DetectedSecret
            from ciris_engine.schemas.foundational_schemas_v1 import SensitivityLevel
            
            # Convert string sensitivity to enum
            sensitivity_enum = SensitivityLevel(sensitivity)
            
            detected_secret = DetectedSecret(
                secret_uuid=uuid,
                original_value=value,
                pattern_name=pattern,
                description=desc,
                sensitivity=sensitivity_enum,
                context_hint="test",
                replacement_text=f"{{SECRET:{uuid}:{desc}}}"
            )
            await temp_store.store_secret(detected_secret)
            
        # List all secrets
        all_secrets = await temp_store.list_secrets()
        assert len(all_secrets) == 3
        
        # List by pattern
        api_secrets = await temp_store.list_secrets(pattern_filter="api_keys")
        assert len(api_secrets) == 1
        assert api_secrets[0].description == "API Key"
        
        # List by sensitivity
        high_secrets = await temp_store.list_secrets(sensitivity_filter="HIGH")
        assert len(high_secrets) == 2
        
    @pytest.mark.asyncio
    async def test_rate_limiting(self, temp_store, sample_detected_secret):
        """Test rate limiting functionality."""
        # Use very low limits for testing
        temp_store.max_accesses_per_minute = 2
        temp_store.max_accesses_per_hour = 5
        
        original_value = "test_secret"
        await temp_store.store_secret(sample_detected_secret)
        
        # Should work for first few accesses
        for i in range(2):
            retrieved = await temp_store.retrieve_secret(
                sample_detected_secret.secret_uuid
            )
            assert retrieved is not None
            
        # Should be rate limited now
        retrieved = await temp_store.retrieve_secret(sample_detected_secret.secret_uuid)
        assert retrieved is None
        
    @pytest.mark.asyncio
    async def test_rate_limiting_enforcement(self, temp_store, sample_detected_secret):
        """Test that rate limiting is enforced."""
        temp_store.max_accesses_per_minute = 2
        
        original_value = "test_secret"
        await temp_store.store_secret(sample_detected_secret)
        
        # First access (should work)
        retrieved = await temp_store.retrieve_secret(sample_detected_secret.secret_uuid)
        assert retrieved is not None
        
        # Second access (should work)  
        retrieved = await temp_store.retrieve_secret(sample_detected_secret.secret_uuid)
        assert retrieved is not None
        
        # Third access (should be rate limited)
        retrieved = await temp_store.retrieve_secret(sample_detected_secret.secret_uuid)
        assert retrieved is None
        
    @pytest.mark.asyncio
    async def test_secret_replacement_in_store(self, temp_store):
        """Test that storing with same UUID replaces existing secret."""
        from ciris_engine.schemas.secrets_schemas_v1 import DetectedSecret
        from ciris_engine.schemas.foundational_schemas_v1 import SensitivityLevel
        
        # Create first secret
        secret1 = DetectedSecret(
            secret_uuid="same-uuid",
            original_value="first_value",
            pattern_name="api_keys",
            description="First Secret",
            sensitivity=SensitivityLevel.HIGH,
            context_hint="first",
            replacement_text="{SECRET:same-uuid:First Secret}"
        )
        await temp_store.store_secret(secret1)
        
        # Create second secret with same UUID
        secret2 = DetectedSecret(
            secret_uuid="same-uuid",
            original_value="second_value",
            pattern_name="passwords",
            description="Second Secret",
            sensitivity=SensitivityLevel.CRITICAL,
            context_hint="second",
            replacement_text="{SECRET:same-uuid:Second Secret}"
        )
        await temp_store.store_secret(secret2)
        
        # Should only have one secret
        all_secrets = await temp_store.list_secrets()
        assert len(all_secrets) == 1
        
        # Should be the second secret
        retrieved = await temp_store.retrieve_secret("same-uuid")
        assert retrieved.description == "Second Secret"
        assert retrieved.sensitivity_level == SensitivityLevel.CRITICAL
        
        decrypted = await temp_store.decrypt_secret_value(retrieved)
        assert decrypted == "second_value"
        
    @pytest.mark.asyncio
    async def test_concurrent_access(self, temp_store, sample_detected_secret):
        """Test concurrent access to secrets store."""
        original_value = "concurrent_test_secret"
        await temp_store.store_secret(sample_detected_secret)
        
        # Create multiple concurrent retrieval tasks
        async def retrieve_secret(user_id):
            return await temp_store.retrieve_secret(
                sample_detected_secret.secret_uuid
            )
            
        # Run 5 concurrent retrievals
        tasks = [retrieve_secret(i) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        # All should succeed (different users)
        for result in results:
            assert result is not None
            assert result.secret_uuid == sample_detected_secret.secret_uuid
            
        # Check final access count
        final_retrieved = await temp_store.retrieve_secret(sample_detected_secret.secret_uuid)
        # Should be 6 total (5 concurrent + 1 final)
        assert final_retrieved.access_count == 6

    @pytest.mark.asyncio
    async def test_reencrypt_all_empty_store(self, temp_store):
        """Test re-encryption with no secrets in store."""
        new_key = b"new_master_key_32_bytes_long!!" # 33 bytes - fix this
        new_key = b"new_master_key_exactly_32bytes!!"  # Exactly 32 bytes
        result = await temp_store.reencrypt_all(new_key)
        assert result is True
        
    @pytest.mark.asyncio
    async def test_reencrypt_all_with_secrets(self, temp_store, sample_detected_secret):
        """Test re-encryption of existing secrets."""
        # Store a secret
        original_secret = await temp_store.store_secret(sample_detected_secret)
        original_value = sample_detected_secret.original_value
        
        # Verify it can be retrieved and decrypted
        retrieved_before = await temp_store.retrieve_secret(sample_detected_secret.secret_uuid)
        decrypted_before = await temp_store.decrypt_secret_value(retrieved_before)
        assert decrypted_before == original_value
        
        # Store the old encryption data for comparison
        old_encrypted_value = retrieved_before.encrypted_value
        old_salt = retrieved_before.salt
        old_nonce = retrieved_before.nonce
        
        # Re-encrypt with new key
        new_key = b"new_master_key_exactly_32bytes!!"  # Exactly 32 bytes
        result = await temp_store.reencrypt_all(new_key)
        assert result is True
        
        # Verify secret can still be retrieved and decrypted with new key
        retrieved_after = await temp_store.retrieve_secret(sample_detected_secret.secret_uuid)
        assert retrieved_after is not None
        decrypted_after = await temp_store.decrypt_secret_value(retrieved_after)
        assert decrypted_after == original_value
        
        # Verify encryption data has changed
        assert retrieved_after.encrypted_value != old_encrypted_value
        assert retrieved_after.salt != old_salt
        assert retrieved_after.nonce != old_nonce
        assert retrieved_after.encryption_key_ref == "master_key_v2"
        
    @pytest.mark.asyncio
    async def test_reencrypt_all_multiple_secrets(self, temp_store):
        """Test re-encryption of multiple secrets."""
        # Store multiple secrets
        secrets_data = [
            ("uuid1", "secret_value_1", "API Key 1", "api_keys"),
            ("uuid2", "secret_value_2", "Password 1", "passwords"),
            ("uuid3", "secret_value_3", "Token 1", "bearer_tokens")
        ]
        
        stored_secrets = []
        for uuid, value, desc, pattern in secrets_data:
            from ciris_engine.schemas.secrets_schemas_v1 import DetectedSecret
            from ciris_engine.schemas.foundational_schemas_v1 import SensitivityLevel
            
            detected_secret = DetectedSecret(
                secret_uuid=uuid,
                original_value=value,
                pattern_name=pattern,
                description=desc,
                sensitivity=SensitivityLevel.HIGH,
                context_hint="test",
                replacement_text=f"{{SECRET:{uuid}:{desc}}}"
            )
            await temp_store.store_secret(detected_secret)
            stored_secrets.append((uuid, value))
        
        # Re-encrypt all
        new_key = b"new_master_key_exactly_32bytes!!"  # Exactly 32 bytes
        result = await temp_store.reencrypt_all(new_key)
        assert result is True
        
        # Verify all secrets can still be decrypted
        for uuid, original_value in stored_secrets:
            retrieved = await temp_store.retrieve_secret(uuid)
            assert retrieved is not None
            decrypted = await temp_store.decrypt_secret_value(retrieved)
            assert decrypted == original_value
            assert retrieved.encryption_key_ref == "master_key_v2"
            
    @pytest.mark.asyncio 
    async def test_reencrypt_all_partial_failure(self, temp_store):
        """Test re-encryption when one secret fails to decrypt."""
        # Store a valid secret
        from ciris_engine.schemas.secrets_schemas_v1 import DetectedSecret
        from ciris_engine.schemas.foundational_schemas_v1 import SensitivityLevel
        
        valid_secret = DetectedSecret(
            secret_uuid="valid-uuid",
            original_value="valid_secret",
            pattern_name="api_keys",
            description="Valid Secret",
            sensitivity=SensitivityLevel.HIGH,
            context_hint="test",
            replacement_text="{SECRET:valid-uuid:Valid Secret}"
        )
        await temp_store.store_secret(valid_secret)
        
        # Manually corrupt a secret in the database to simulate decryption failure
        import sqlite3
        with sqlite3.connect(temp_store.db_path) as conn:
            conn.execute("""
                INSERT INTO secrets (
                    secret_uuid, encrypted_value, encryption_key_ref, salt, nonce,
                    description, sensitivity_level, detected_pattern, context_hint,
                    created_at, access_count, auto_decapsulate_for_actions, manual_access_only
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "corrupted-uuid",
                b"corrupted_data",  # Invalid encrypted data
                "master_key_v1",
                b"fake_salt_16byt",
                b"fake_nonce_",
                "Corrupted Secret",
                "HIGH",
                "api_keys",
                "test",
                "2023-01-01T00:00:00",
                0,
                "tool",
                0
            ))
            conn.commit()
        
        # Re-encryption should fail due to corrupted secret
        new_key = b"new_master_key_exactly_32bytes!!"  # Exactly 32 bytes
        result = await temp_store.reencrypt_all(new_key)
        assert result is False