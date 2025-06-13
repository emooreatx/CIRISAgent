"""
Test suite for secrets tools functionality.

Tests RECALL_SECRET, UPDATE_SECRETS_FILTER, and LIST_SECRETS tools.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from typing import Dict, Any

from ciris_engine.secrets.tools import (
    SecretsTools, 
    RecallSecretParams, 
    UpdateSecretsFilterParams,
    register_secrets_tools
)
from ciris_engine.secrets.service import SecretsService
from ciris_engine.schemas.config_schemas_v1 import SecretPattern, SecretsDetectionConfig
from ciris_engine.schemas.tool_schemas_v1 import ToolExecutionStatus
from ciris_engine.adapters.tool_registry import ToolRegistry


@pytest.fixture
def mock_secrets_service():
    """Mock SecretsService for testing."""
    service = AsyncMock(spec=SecretsService)
    service.store = AsyncMock()
    service.filter = MagicMock()
    service.audit_service = AsyncMock()
    return service


@pytest.fixture
def secrets_tools(mock_secrets_service):
    """SecretsTools instance with mocked service."""
    return SecretsTools(mock_secrets_service)


@pytest.mark.asyncio
class TestSecretsTools:
    """Test SecretsTools functionality."""
    
    async def test_recall_secret_success_metadata_only(self, secrets_tools, mock_secrets_service):
        """Test successful secret recall without decryption."""
        # Setup mock response
        from ciris_engine.schemas.secrets_schemas_v1 import SecretRecord
        mock_record = SecretRecord(
            secret_uuid="test-uuid-123",
            encrypted_value=b"encrypted_data",
            encryption_key_ref="key_ref_123",
            salt=b"salt_bytes",
            nonce=b"nonce_bytes",
            description="Test API key",
            sensitivity_level="HIGH",
            detected_pattern="api_keys",
            context_hint="Test API key",
            created_at=datetime.now(),
            access_count=0,
            last_accessed=None
        )
        mock_secrets_service.store.retrieve_secret.return_value = mock_record
        
        # Test parameters
        params = RecallSecretParams(
            secret_uuid="test-uuid-123",
            purpose="Testing secret recall",
            decrypt=False
        )
        
        # Execute
        result = await secrets_tools.recall_secret(params)
        
        # Verify
        assert result.execution_status == ToolExecutionStatus.SUCCESS
        assert result.tool_name == "recall_secret"
        assert result.result_data["secret_uuid"] == "test-uuid-123"
        assert "decrypted_value" not in result.result_data
        
        # Verify store retrieve was called
        mock_secrets_service.store.retrieve_secret.assert_called_once_with("test-uuid-123")
        
        # Verify audit service was called for metadata access
        mock_secrets_service.audit_service.log_action.assert_called_once()
        
    async def test_recall_secret_success_with_decryption(self, secrets_tools, mock_secrets_service):
        """Test successful secret recall with decryption."""
        # Setup mock responses
        from ciris_engine.schemas.secrets_schemas_v1 import SecretRecord
        mock_record = SecretRecord(
            secret_uuid="test-uuid-123",
            encrypted_value=b"encrypted_data",
            encryption_key_ref="key_ref_123",
            salt=b"salt_bytes",
            nonce=b"nonce_bytes",
            description="Test API key",
            sensitivity_level="HIGH",
            detected_pattern="api_keys",
            context_hint="Test API key",
            created_at=datetime.now(),
            access_count=1,
            last_accessed=datetime.now()
        )
        mock_secrets_service.store.retrieve_secret.return_value = mock_record
        mock_secrets_service.store.get_secret.return_value = mock_record
        mock_secrets_service.store.decrypt_secret_value.return_value = "sk-1234567890abcdef"
        
        # Test parameters
        params = RecallSecretParams(
            secret_uuid="test-uuid-123",
            purpose="Testing secret decryption",
            decrypt=True
        )
        
        # Execute
        result = await secrets_tools.recall_secret(params)
        
        # Verify
        assert result.execution_status == ToolExecutionStatus.SUCCESS
        assert result.result_data["decrypted_value"] == "sk-1234567890abcdef"
        assert result.metadata["decrypted"] is True
        
        # Verify decrypt was called
        mock_secrets_service.store.get_secret.assert_called_once_with("test-uuid-123")
        mock_secrets_service.store.decrypt_secret_value.assert_called_once_with(mock_record)
        
    async def test_recall_secret_not_found(self, secrets_tools, mock_secrets_service):
        """Test secret recall when secret doesn't exist."""
        mock_secrets_service.store.retrieve_secret.return_value = None
        
        params = RecallSecretParams(
            secret_uuid="nonexistent-uuid",
            purpose="Testing not found",
            decrypt=False
        )
        
        result = await secrets_tools.recall_secret(params)
        
        assert result.execution_status == ToolExecutionStatus.NOT_FOUND
        assert "not found" in result.error_message.lower()
        
    async def test_update_secrets_filter_add_pattern(self, secrets_tools, mock_secrets_service):
        """Test adding a new pattern to secrets filter."""
        pattern = SecretPattern(
            name="test_pattern",
            regex=r"test_\d+",
            description="Test pattern",
            sensitivity="MEDIUM",
            context_hint="Test context"
        )
        
        params = UpdateSecretsFilterParams(
            operation="add_pattern",
            pattern=pattern
        )
        
        result = await secrets_tools.update_secrets_filter(params)
        
        assert result.execution_status == ToolExecutionStatus.SUCCESS
        assert result.result_data["pattern_added"] == "test_pattern"
        mock_secrets_service.filter.add_custom_pattern.assert_called_once_with(pattern)
        
    async def test_update_secrets_filter_get_current(self, secrets_tools, mock_secrets_service):
        """Test getting current filter configuration."""
        # Setup mock responses
        mock_config = {"detection_config": "test_data"}
        mock_stats = {"total_patterns": 3, "default_patterns": 2, "custom_patterns": 1}
        mock_secrets_service.filter.export_config.return_value = mock_config
        mock_secrets_service.filter.get_pattern_stats.return_value = mock_stats
        
        params = UpdateSecretsFilterParams(operation="get_current")
        
        result = await secrets_tools.update_secrets_filter(params)
        
        assert result.execution_status == ToolExecutionStatus.SUCCESS
        assert "config" in result.result_data
        assert "stats" in result.result_data
        
    async def test_list_secrets(self, secrets_tools, mock_secrets_service):
        """Test listing stored secrets."""
        # Setup mock response
        from ciris_engine.schemas.secrets_schemas_v1 import SecretRecord
        mock_secrets = [
            SecretRecord(
                secret_uuid="uuid-1",
                encrypted_value=b"data1",
                encryption_key_ref="key1",
                salt=b"salt1",
                nonce=b"nonce1",
                description="API Key 1",
                sensitivity_level="HIGH",
                detected_pattern="api_keys",
                context_hint="API Key 1",
                created_at=datetime.now(),
                access_count=5,
                last_accessed=datetime.now()
            ),
            SecretRecord(
                secret_uuid="uuid-2",
                encrypted_value=b"data2",
                encryption_key_ref="key2",
                salt=b"salt2",
                nonce=b"nonce2",
                description="Password 1",
                sensitivity_level="CRITICAL",
                detected_pattern="passwords",
                context_hint="Password 1",
                created_at=datetime.now(),
                access_count=2,
                last_accessed=None
            )
        ]
        mock_secrets_service.store.list_all_secrets.return_value = mock_secrets
        
        result = await secrets_tools.list_secrets(include_sensitive=True)
        
        assert result.execution_status == ToolExecutionStatus.SUCCESS
        assert result.result_data["total_count"] == 2
        assert len(result.result_data["secrets"]) == 2
        assert result.result_data["secrets"][0]["uuid"] == "uuid-1"
        assert result.result_data["secrets"][0]["context_hint"] == "API Key 1"


class TestSecretsToolsRegistration:
    """Test secrets tools registration."""
    
    def test_register_secrets_tools(self, mock_secrets_service):
        """Test that secrets tools are properly registered."""
        registry = ToolRegistry()
        register_secrets_tools(registry, mock_secrets_service)
        
        # Verify tools were registered
        assert registry.get_tool_schema("recall_secret") is not None
        assert registry.get_tool_schema("update_secrets_filter") is not None
        assert registry.get_tool_schema("list_secrets") is not None
        
        # Verify handlers were registered
        assert registry.get_handler("recall_secret") is not None
        assert registry.get_handler("update_secrets_filter") is not None
        assert registry.get_handler("list_secrets") is not None
        
        # Test schema structure
        recall_schema = registry.get_tool_schema("recall_secret")
        assert "secret_uuid" in recall_schema
        assert "purpose" in recall_schema
        assert "decrypt" in recall_schema


class TestSecretsToolsIntegration:
    """Integration tests with real secrets service."""
    
    @pytest.mark.asyncio
    async def test_full_recall_workflow(self):
        """Test full workflow of storing and recalling a secret."""
        # This would need a real SecretsService instance
        # Implementation depends on test database setup
        pass