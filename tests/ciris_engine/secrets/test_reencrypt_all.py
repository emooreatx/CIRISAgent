"""Tests specifically for the reencrypt_all functionality."""
import pytest
import tempfile
import sqlite3
from pathlib import Path

from ciris_engine.secrets.store import SecretsStore, SecretsEncryption
from ciris_engine.schemas.secrets_schemas_v1 import DetectedSecret
from ciris_engine.schemas.foundational_schemas_v1 import SensitivityLevel


class TestReencryptAll:
    """Test the reencrypt_all method specifically."""
    
    @pytest.fixture
    def temp_store(self):
        """Create temporary secrets store."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_secrets.db"
            store = SecretsStore(str(db_path))
            yield store
    
    @pytest.fixture
    def sample_secret(self):
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
    
    def test_key_validation(self):
        """Test that our test key is valid."""
        test_key = b"new_master_key_exactly_32bytes!!"  # 32 bytes
        assert len(test_key) == 32
        
        # Should be able to create encryption instance
        enc = SecretsEncryption(test_key)
        assert enc.master_key == test_key
    
    @pytest.mark.asyncio
    async def test_reencrypt_all_empty_store(self, temp_store):
        """Test re-encryption with no secrets in store."""
        new_key = b"new_master_key_exactly_32bytes!!"
        result = await temp_store.reencrypt_all(new_key)
        assert result is True
        
    @pytest.mark.asyncio
    async def test_reencrypt_all_single_secret(self, temp_store, sample_secret):
        """Test re-encryption of a single secret."""
        # Store the secret
        await temp_store.store_secret(sample_secret)
        
        # Verify it can be retrieved and decrypted
        retrieved_before = await temp_store.retrieve_secret(sample_secret.secret_uuid)
        decrypted_before = await temp_store.decrypt_secret_value(retrieved_before)
        assert decrypted_before == sample_secret.original_value
        
        # Store old encryption data for comparison
        old_encrypted = retrieved_before.encrypted_value
        old_salt = retrieved_before.salt
        old_nonce = retrieved_before.nonce
        
        # Re-encrypt with new key
        new_key = b"new_master_key_exactly_32bytes!!"
        result = await temp_store.reencrypt_all(new_key)
        assert result is True
        
        # Verify secret can still be retrieved and decrypted
        retrieved_after = await temp_store.retrieve_secret(sample_secret.secret_uuid)
        assert retrieved_after is not None
        decrypted_after = await temp_store.decrypt_secret_value(retrieved_after)
        assert decrypted_after == sample_secret.original_value
        
        # Verify encryption data has changed
        assert retrieved_after.encrypted_value != old_encrypted
        assert retrieved_after.salt != old_salt
        assert retrieved_after.nonce != old_nonce
        assert retrieved_after.encryption_key_ref == "master_key_v2"
        
    @pytest.mark.asyncio
    async def test_reencrypt_all_multiple_secrets(self, temp_store):
        """Test re-encryption of multiple secrets."""
        secrets_data = [
            ("uuid1", "secret_value_1", "API Key 1"),
            ("uuid2", "secret_value_2", "Password 1"),
            ("uuid3", "secret_value_3", "Token 1")
        ]
        
        # Store multiple secrets
        for uuid, value, desc in secrets_data:
            secret = DetectedSecret(
                secret_uuid=uuid,
                original_value=value,
                pattern_name="api_keys",
                description=desc,
                sensitivity=SensitivityLevel.HIGH,
                context_hint="test",
                replacement_text=f"{{SECRET:{uuid}:{desc}}}"
            )
            await temp_store.store_secret(secret)
        
        # Re-encrypt all
        new_key = b"new_master_key_exactly_32bytes!!"
        result = await temp_store.reencrypt_all(new_key)
        assert result is True
        
        # Verify all secrets can still be decrypted
        for uuid, original_value, _ in secrets_data:
            retrieved = await temp_store.retrieve_secret(uuid)
            assert retrieved is not None
            decrypted = await temp_store.decrypt_secret_value(retrieved)
            assert decrypted == original_value
            assert retrieved.encryption_key_ref == "master_key_v2"
            
    @pytest.mark.asyncio
    async def test_reencrypt_all_corrupted_secret_fails(self, temp_store):
        """Test that re-encryption fails if a secret is corrupted."""
        # Store a valid secret first
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
        
        # Manually insert corrupted secret data
        with sqlite3.connect(temp_store.db_path) as conn:
            conn.execute("""
                INSERT INTO secrets (
                    secret_uuid, encrypted_value, encryption_key_ref, salt, nonce,
                    description, sensitivity_level, detected_pattern, context_hint,
                    created_at, access_count, auto_decapsulate_for_actions, manual_access_only
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "corrupted-uuid",
                b"invalid_encrypted_data",
                "master_key_v1",
                b"fake_salt_16byte",
                b"fake_nonce12",
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
        new_key = b"new_master_key_exactly_32bytes!!"
        result = await temp_store.reencrypt_all(new_key)
        assert result is False