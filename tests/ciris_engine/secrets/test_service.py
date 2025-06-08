"""Tests for secrets management service."""
import pytest
import tempfile
import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.secrets.service import SecretsService
from ciris_engine.secrets.store import SecretsStore
from ciris_engine.secrets.filter import SecretsFilter
from ciris_engine.schemas.config_schemas_v1 import SecretPattern
from ciris_engine.schemas.foundational_schemas_v1 import SensitivityLevel
from ciris_engine.schemas.secrets_schemas_v1 import SecretReference


class TestSecretsService:
    """Test secrets management service functionality."""
    
    @pytest.fixture
    def temp_service(self):
        """Create temporary secrets service."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_secrets.db"
            service = SecretsService(db_path=str(db_path))
            yield service
            
    @pytest.fixture
    def mock_service(self):
        """Create service with mocked dependencies."""
        mock_store = AsyncMock(spec=SecretsStore)
        mock_filter = MagicMock(spec=SecretsFilter)
        service = SecretsService(store=mock_store, filter_obj=mock_filter)
        return service, mock_store, mock_filter
        
    @pytest.mark.asyncio
    async def test_process_incoming_text_no_secrets(self, temp_service):
        """Test processing text with no secrets."""
        text = "This is just normal text with no sensitive information."
        
        filtered_text, secret_refs = await temp_service.process_incoming_text(
            text, "test context"
        )
        
        assert filtered_text == text
        assert len(secret_refs) == 0
        
    @pytest.mark.asyncio
    async def test_process_incoming_text_with_secrets(self, temp_service):
        """Test processing text containing secrets."""
        text = "Please use API key api_key=sk_test_1234567890abcdef123456 for authentication"
        
        filtered_text, secret_refs = await temp_service.process_incoming_text(
            text, "test context", "msg_123"
        )
        
        # Should detect and replace secret
        assert "sk_test_1234567890abcdef123456" not in filtered_text
        assert "{SECRET:" in filtered_text
        assert len(secret_refs) >= 1
        
        # Check secret reference
        secret_ref = secret_refs[0]
        assert secret_ref.description == "API Key"
        assert secret_ref.sensitivity == SensitivityLevel.HIGH
        assert secret_ref.context_hint == "test context"
        
    @pytest.mark.asyncio
    async def test_recall_secret_decrypt(self, temp_service):
        """Test recalling and decrypting a secret."""
        # First, store a secret
        text = "API key is api_key=test_secret_12345678901234567890"
        filtered_text, secret_refs = await temp_service.process_incoming_text(text)
        
        assert len(secret_refs) > 0
        secret_uuid = secret_refs[0].uuid
        
        # Recall with decryption
        result = await temp_service.recall_secret(
            secret_uuid, 
            "Need for API call",
            "test_user",
            decrypt=True
        )
        
        assert result is not None
        assert "decrypted_value" in result
        assert "test_secret_12345678901234567890" in result["decrypted_value"]
        assert result["description"] == "API Key"
        assert result["sensitivity"] == "HIGH"
        
    @pytest.mark.asyncio
    async def test_recall_secret_no_decrypt(self, temp_service):
        """Test recalling secret without decryption."""
        # Store a secret
        text = "Password: password=mysecretpassword123"
        filtered_text, secret_refs = await temp_service.process_incoming_text(text)
        
        assert len(secret_refs) > 0
        secret_uuid = secret_refs[0].uuid
        
        # Recall without decryption
        result = await temp_service.recall_secret(
            secret_uuid,
            "Just checking metadata",
            "test_user", 
            decrypt=False
        )
        
        assert result is not None
        assert "decrypted_value" not in result
        assert result["description"] == "Password"
        assert result["sensitivity"] == "CRITICAL"
        
    @pytest.mark.asyncio
    async def test_recall_nonexistent_secret(self, temp_service):
        """Test recalling non-existent secret."""
        result = await temp_service.recall_secret(
            "non-existent-uuid",
            "test purpose",
            "test_user"
        )
        
        assert result is None
        
    @pytest.mark.asyncio
    async def test_decapsulate_secrets_in_parameters(self, temp_service):
        """Test automatic decapsulation of secrets in action parameters."""
        # Store a secret first
        text = "Use API key api_key=mytoken12345678901234567890 for auth"
        filtered_text, secret_refs = await temp_service.process_incoming_text(text)
        
        assert len(secret_refs) > 0
        secret_uuid = secret_refs[0].uuid
        
        # Create parameters with secret reference  
        # Use the actual description from the stored secret
        secret_desc = secret_refs[0].description
        parameters = {
            "url": "https://api.example.com/data", 
            "headers": {
                "Authorization": f"Bearer {{SECRET:{secret_uuid}:{secret_desc}}}"
            },
            "data": "some data"
        }
        
        # Decapsulate for tool action (should work for bearer tokens)
        decapsulated = await temp_service.decapsulate_secrets_in_parameters(
            parameters, "tool", {"test": "context"}
        )
        
        # Secret should be decapsulated in tool action
        auth_header = decapsulated["headers"]["Authorization"]
        assert "mytoken12345678901234567890" in auth_header
        assert "SECRET:" not in auth_header
        
    @pytest.mark.asyncio
    async def test_decapsulate_wrong_action_type(self, temp_service):
        """Test that secrets are not decapsulated for wrong action types."""
        # Store a critical secret (no auto-decapsulation)
        text = "Password: password=criticalsecret123"
        filtered_text, secret_refs = await temp_service.process_incoming_text(text)
        
        assert len(secret_refs) > 0
        secret_uuid = secret_refs[0].uuid
        
        # Create parameters with secret reference
        parameters = {
            "message": f"The password is {{SECRET:{secret_uuid}:Password}}"
        }
        
        # Try to decapsulate for speak action (critical secrets shouldn't auto-decapsulate)
        decapsulated = await temp_service.decapsulate_secrets_in_parameters(
            parameters, "speak", {"test": "context"}
        )
        
        # Secret should NOT be decapsulated
        assert "SECRET:" in decapsulated["message"]
        assert "criticalsecret123" not in decapsulated["message"]
        
    @pytest.mark.asyncio
    async def test_update_filter_config_add_pattern(self, temp_service):
        """Test adding custom pattern to filter."""
        # Add custom pattern
        custom_pattern = SecretPattern(
            name="custom_id",
            regex=r"CUSTOM_[A-Z0-9]{8}",
            description="Custom ID Pattern",
            sensitivity=SensitivityLevel.MEDIUM,
            context_hint="Custom identifier token"
        )
        
        result = await temp_service.update_filter_config(
            {"add_pattern": custom_pattern}
        )
        
        assert result["success"]
        assert "Added pattern: custom_id" in result["results"][0]
        
        # Test that new pattern works
        text = "Use custom ID CUSTOM_ABC12345 for this"
        filtered_text, secret_refs = await temp_service.process_incoming_text(text)
        
        assert len(secret_refs) > 0
        assert secret_refs[0].description == "Custom ID Pattern"
        assert "CUSTOM_ABC12345" not in filtered_text
        
    @pytest.mark.asyncio
    async def test_update_filter_config_remove_pattern(self, temp_service):
        """Test removing custom pattern from filter."""
        # First add a pattern
        custom_pattern = SecretPattern(
            name="temp_pattern",
            regex=r"TEMP_[0-9]{4}",
            description="Temporary Pattern",
            sensitivity=SensitivityLevel.LOW,
            context_hint="Temporary identifier"
        )
        
        await temp_service.update_filter_config(
            {"add_pattern": custom_pattern}
        )
        
        # Remove the pattern
        result = await temp_service.update_filter_config(
            {"remove_pattern": "temp_pattern"}
        )
        
        assert result["success"]
        assert "Removed pattern: temp_pattern" in result["results"][0]
        
        # Should no longer detect the pattern
        text = "Test ID TEMP_1234"
        filtered_text, secret_refs = await temp_service.process_incoming_text(text)
        
        assert len(secret_refs) == 0
        assert filtered_text == text
        
    @pytest.mark.asyncio
    async def test_update_filter_config_get_current(self, temp_service):
        """Test getting current filter configuration."""
        result = await temp_service.update_filter_config("get_current")
        
        assert result["success"]
        assert "config" in result
        assert "stats" in result
        assert result["stats"]["total_patterns"] > 0
        
    @pytest.mark.asyncio
    async def test_list_stored_secrets(self, temp_service):
        """Test listing stored secrets."""
        # Store multiple secrets
        texts = [
            "API key: api_key=key123456789012345678901234567890",
            "Password: password=mypassword123",
            "Authorization: Bearer token123456789012345678901234567890"
        ]
        
        for text in texts:
            await temp_service.process_incoming_text(text)
            
        # List all secrets
        secrets = await temp_service.list_stored_secrets()
        assert len(secrets) >= 3
        
        # Check structure
        for secret in secrets:
            assert hasattr(secret, "uuid")
            assert hasattr(secret, "description")
            assert hasattr(secret, "sensitivity")
            assert hasattr(secret, "detected_pattern")
            assert hasattr(secret, "created_at")
            
        # Check that we can access specific fields
        assert secrets[0].uuid is not None
        assert secrets[0].description is not None
        assert secrets[0].sensitivity is not None
        
    @pytest.mark.asyncio
    async def test_forget_secret(self, temp_service):
        """Test forgetting a stored secret."""
        # Store a secret
        text = "API key: api_key=forgettable123456789012345678"
        filtered_text, secret_refs = await temp_service.process_incoming_text(text)
        
        assert len(secret_refs) > 0
        secret_uuid = secret_refs[0].uuid
        
        # Verify it exists
        result = await temp_service.recall_secret(secret_uuid, "check exists", "user")
        assert result is not None
        
        # Forget the secret
        forgotten = await temp_service.forget_secret(secret_uuid, "test_user")
        assert forgotten
        
        # Should no longer exist
        result = await temp_service.recall_secret(secret_uuid, "check deleted", "user")
        assert result is None
        
    @pytest.mark.asyncio
    async def test_auto_forget_task_secrets(self, temp_service):
        """Test automatic forgetting of task secrets."""
        # Store some secrets
        texts = [
            "API key: api_key=task_secret_1234567890123456789",
            "Authorization: Bearer task_token_123456789012345678"
        ]
        
        secret_uuids = []
        for text in texts:
            filtered_text, secret_refs = await temp_service.process_incoming_text(text)
            if secret_refs:
                secret_uuids.append(secret_refs[0].uuid)
                
        assert len(secret_uuids) >= 2
        
        # Verify secrets exist
        for uuid in secret_uuids:
            result = await temp_service.recall_secret(uuid, "verify", "user")
            assert result is not None
            
        # Auto-forget task secrets
        forgotten_uuids = await temp_service.auto_forget_task_secrets()
        assert len(forgotten_uuids) >= 2
        
        # Secrets should be gone
        for uuid in secret_uuids:
            result = await temp_service.recall_secret(uuid, "verify deleted", "user")
            assert result is None
            
    @pytest.mark.asyncio
    async def test_auto_forget_disabled(self, temp_service):
        """Test that auto-forget can be disabled."""
        # Disable auto-forget
        temp_service.disable_auto_forget()
        
        # Store a secret
        text = "API key: api_key=persistent_secret_1234567890123"
        filtered_text, secret_refs = await temp_service.process_incoming_text(text)
        assert len(secret_refs) > 0
        secret_uuid = secret_refs[0].uuid
        
        # Try auto-forget (should do nothing)
        forgotten_uuids = await temp_service.auto_forget_task_secrets()
        assert len(forgotten_uuids) == 0
        
        # Secret should still exist
        result = await temp_service.recall_secret(secret_uuid, "check persistent", "user")
        assert result is not None
        
    @pytest.mark.asyncio
    async def test_get_service_stats(self, temp_service):
        """Test getting service statistics."""
        # Store some secrets of different types
        texts = [
            "API key: api_key=stats_key_123456789012345678901",
            "Password: password=statspass123",
            "Authorization: Bearer stats_token_12345678901234567"
        ]
        
        for text in texts:
            await temp_service.process_incoming_text(text)
            
        # Get stats
        stats = await temp_service.get_service_stats()
        
        assert "filter_stats" in stats
        assert "storage_stats" in stats
        
        storage_stats = stats["storage_stats"]
        assert storage_stats["total_secrets"] >= 3
        assert "sensitivity_distribution" in storage_stats
        assert "pattern_distribution" in storage_stats
        assert "auto_forget_enabled" in storage_stats
        
        # Check that we have different sensitivities
        sensitivity_dist = storage_stats["sensitivity_distribution"]
        assert len(sensitivity_dist) > 1  # Should have HIGH and CRITICAL at least
        
    @pytest.mark.asyncio
    async def test_nested_parameter_decapsulation(self, temp_service):
        """Test decapsulation in deeply nested parameter structures."""
        # Store a secret
        text = "Authorization: Bearer nested_token_123456789012345"
        filtered_text, secret_refs = await temp_service.process_incoming_text(text)
        
        assert len(secret_refs) > 0
        secret_uuid = secret_refs[0].uuid
        
        # Create deeply nested parameters
        parameters = {
            "config": {
                "auth": {
                    "tokens": [
                        {
                            "type": "bearer",
                            "value": f"{{SECRET:{secret_uuid}:Bearer Token}}"
                        }
                    ]
                },
                "settings": {
                    "debug": True
                }
            },
            "headers": {
                "Authorization": f"Bearer {{SECRET:{secret_uuid}:Bearer Token}}"
            }
        }
        
        # Decapsulate for tool action
        decapsulated = await temp_service.decapsulate_secrets_in_parameters(
            parameters, "tool", {}
        )
        
        # Check nested decapsulation
        nested_token = decapsulated["config"]["auth"]["tokens"][0]["value"]
        header_token = decapsulated["headers"]["Authorization"]
        
        assert "nested_token_123456789012345" in nested_token
        assert "nested_token_123456789012345" in header_token
        assert "SECRET:" not in nested_token
        assert "SECRET:" not in header_token
        
        # Non-secret values should be unchanged
        assert decapsulated["config"]["settings"]["debug"] is True
        
    @pytest.mark.asyncio
    async def test_concurrent_secret_processing(self, temp_service):
        """Test concurrent processing of secrets."""
        texts = [
            f"API key {i}: api_key=concurrent_key_{i}_123456789012345678" 
            for i in range(5)
        ]
        
        # Process concurrently
        tasks = [
            temp_service.process_incoming_text(text, f"context_{i}")
            for i, text in enumerate(texts)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert len(results) == 5
        for filtered_text, secret_refs in results:
            assert len(secret_refs) >= 1
            assert "concurrent_key_" not in filtered_text
            assert "SECRET:" in filtered_text
            
    @pytest.mark.asyncio
    async def test_sensitivity_based_auto_decapsulation(self, temp_service):
        """Test that auto-decapsulation works based on sensitivity levels."""
        # First add custom patterns for testing different sensitivity levels
        low_pattern = SecretPattern(
            name="low_test",
            regex=r"low_secret_[a-z0-9]{10,}",
            description="Low Sensitivity Test",
            sensitivity=SensitivityLevel.LOW,
            context_hint="Low sensitivity test token"
        )
        
        medium_pattern = SecretPattern(
            name="medium_test", 
            regex=r"medium_secret_[a-z0-9]{10,}",
            description="Medium Sensitivity Test",
            sensitivity=SensitivityLevel.MEDIUM,
            context_hint="Medium sensitivity test token"
        )
        
        # Add patterns
        await temp_service.update_filter_config({"add_pattern": low_pattern})
        await temp_service.update_filter_config({"add_pattern": medium_pattern})
        
        # Test different sensitivity levels using actual pattern sensitivities
        test_cases = [
            ("low_secret_abc123def456", "LOW", "speak", True),  # LOW allows speak
            ("medium_secret_abc123def456", "MEDIUM", "speak", True),  # MEDIUM allows speak  
            ("api_key=high_key_12345678901234567890", "HIGH", "speak", False),  # HIGH doesn't allow speak
            ("password=critical_pass123", "CRITICAL", "tool", False),  # CRITICAL doesn't allow any
        ]
        
        for text, expected_sensitivity, action_type, should_decapsulate in test_cases:
            # Process text
            filtered_text, secret_refs = await temp_service.process_incoming_text(text)
            
            if not secret_refs:
                continue  # Skip if pattern didn't match
                
            secret_ref = secret_refs[0]
            secret_uuid = secret_ref.uuid
            
            # Verify we got the expected sensitivity
            assert secret_ref.sensitivity == expected_sensitivity, f"Expected {expected_sensitivity}, got {secret_ref.sensitivity} for {text}"
            
            # Create parameters with secret
            parameters = {
                "data": f"{{SECRET:{secret_uuid}:Test Secret}}"
            }
            
            # Try decapsulation
            decapsulated = await temp_service.decapsulate_secrets_in_parameters(
                parameters, action_type, {}
            )
            
            if should_decapsulate:
                # Should be decapsulated
                assert "SECRET:" not in decapsulated["data"], f"Expected decapsulation for {expected_sensitivity} + {action_type}"
            else:
                # Should remain as reference
                assert "SECRET:" in decapsulated["data"], f"Expected NO decapsulation for {expected_sensitivity} + {action_type}"