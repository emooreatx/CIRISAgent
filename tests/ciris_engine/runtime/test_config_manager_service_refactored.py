"""Tests for the refactored ConfigManagerService."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone
from pathlib import Path

from ciris_engine.services.config_manager_service import ConfigManagerService
from ciris_engine.schemas.runtime_control_schemas import (
    ConfigScope, ConfigValidationLevel, ConfigOperationResponse,
    ConfigValidationResponse, AgentProfileInfo, AgentProfileResponse,
    ConfigBackupResponse
)
from ciris_engine.schemas.config_schemas_v1 import AppConfig


class TestConfigManagerServiceRefactored:
    """Test the refactored ConfigManagerService class."""

    @pytest.fixture
    def service(self):
        """Create a service instance."""
        return ConfigManagerService()

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = MagicMock(spec=AppConfig)
        config.model_dump.return_value = {"test": "value"}
        return config

    @pytest.mark.asyncio
    async def test_service_lifecycle(self, service):
        """Test service start/stop lifecycle."""
        with patch('ciris_engine.services.config_manager_service.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_get_config.return_value = mock_config
            
            # Test start
            await service.start()
            assert service._is_running is True
            assert service._config_manager is not None
            
            # Test health check
            is_healthy = await service.is_healthy()
            assert is_healthy is True
            
            # Test stop
            await service.stop()
            assert service._is_running is False

    @pytest.mark.asyncio
    async def test_service_capabilities(self, service):
        """Test service capabilities."""
        capabilities = await service.get_capabilities()
        expected_capabilities = [
            "config.get", "config.update", "config.validate",
            "profile.list", "profile.create", "profile.reload",
            "backup.create", "backup.restore"
        ]
        for cap in expected_capabilities:
            assert cap in capabilities

    @pytest.mark.asyncio
    async def test_get_config_value_full(self, service, mock_config):
        """Test getting full configuration."""
        # Initialize the service first
        with patch('ciris_engine.services.config_manager_service.get_config') as mock_get_config:
            mock_get_config.return_value = mock_config
            await service.start()
            
            result = await service.get_config_value()
            
            assert "test" in result
            mock_config.model_dump.assert_called_once_with(mode="json")

    @pytest.mark.asyncio
    async def test_get_config_value_specific_path(self, service):
        """Test getting specific configuration path."""
        mock_config = MagicMock()
        mock_llm_config = MagicMock()
        mock_llm_config.model_dump.return_value = {"api_key": "test"}
        mock_config.llm_services = mock_llm_config
        
        with patch('ciris_engine.services.config_manager_service.get_config') as mock_get_config:
            mock_get_config.return_value = mock_config
            await service.start()
            
            # Mock the validator to not mask the values for this test
            service._validator.mask_sensitive_values = MagicMock(side_effect=lambda x: x)
            
            result = await service.get_config_value("llm_services", include_sensitive=True)
            
            assert result["path"] == "llm_services"
            assert result["value"] == {"api_key": "test"}

    @pytest.mark.asyncio
    async def test_get_config_value_sensitive_masking(self, service, mock_config):
        """Test that sensitive values are masked."""
        mock_config.model_dump.return_value = {"api_key": "secret123", "normal": "value"}
        
        with patch('ciris_engine.services.config_manager_service.get_config') as mock_get_config:
            mock_get_config.return_value = mock_config
            await service.start()
            
            # Mock the validator method
            service._validator.mask_sensitive_values = MagicMock(return_value={"masked": "data"})
            
            result = await service.get_config_value(include_sensitive=False)
            
            # Should have called validator to mask sensitive values
            service._validator.mask_sensitive_values.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_config_value_success(self, service):
        """Test successful configuration update."""
        mock_config = MagicMock()
        
        with patch('ciris_engine.services.config_manager_service.get_config') as mock_get_config:
            mock_get_config.return_value = mock_config
            await service.start()
            
            # Mock the config manager's update method
            service._config_manager.update_config = AsyncMock()
            
            # Mock get_config_value to return old value
            with patch.object(service, 'get_config_value', return_value={"value": "old_value"}):
                # Mock validation to pass
                service._validator.validate_config_update = AsyncMock(
                    return_value=ConfigValidationResponse(valid=True, errors=[], warnings=[])
                )
                
                result = await service.update_config_value(
                    "test.path", "new_value", reason="Testing"
                )
                
                assert result.success is True
                assert result.operation == "update_config"
                assert result.path == "test.path"
                assert result.new_value == "new_value"
                service._config_manager.update_config.assert_called_once_with("test.path", "new_value")

    @pytest.mark.asyncio
    async def test_update_config_value_validation_failure(self, service):
        """Test configuration update with validation failure."""
        with patch.object(service, 'get_config_value', return_value={"value": "old_value"}):
            # Mock validation to fail
            service._validator.validate_config_update = AsyncMock(
                return_value=ConfigValidationResponse(
                    valid=False, 
                    errors=["Invalid value"], 
                    warnings=[]
                )
            )
            
            result = await service.update_config_value(
                "test.path", "invalid_value", 
                validation_level=ConfigValidationLevel.STRICT
            )
            
            assert result.success is False
            assert "Validation failed" in result.error

    @pytest.mark.asyncio
    async def test_update_config_value_bypass_validation(self, service):
        """Test configuration update bypassing validation."""
        mock_config = MagicMock()
        
        with patch('ciris_engine.services.config_manager_service.get_config') as mock_get_config:
            mock_get_config.return_value = mock_config
            await service.start()
            
            service._config_manager.update_config = AsyncMock()
            
            with patch.object(service, 'get_config_value', return_value={"value": "old_value"}):
                # Track if validation was called
                service._validator.validate_config_update = AsyncMock()
                
                result = await service.update_config_value(
                    "test.path", "new_value",
                    validation_level=ConfigValidationLevel.BYPASS
                )
                
                assert result.success is True
                # Should not have called validation
                service._validator.validate_config_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_config_delegates(self, service):
        """Test that validate_config delegates to validator."""
        config_data = {"test": "data"}
        expected_response = ConfigValidationResponse(valid=True, errors=[], warnings=[])
        service._validator.validate_config = AsyncMock(return_value=expected_response)
        
        result = await service.validate_config(config_data)
        
        assert result == expected_response
        service._validator.validate_config.assert_called_once_with(
            config_data, None, None
        )

    @pytest.mark.asyncio
    async def test_list_profiles_delegates(self, service):
        """Test that list_profiles delegates to profile manager."""
        mock_config = MagicMock()
        
        with patch('ciris_engine.services.config_manager_service.get_config') as mock_get_config:
            mock_get_config.return_value = mock_config
            await service.start()
            
            expected_profiles = [
                AgentProfileInfo(
                    name="test", description="Test profile", file_path="test.yaml",
                    is_active=False, permitted_actions=[], adapter_configs={}
                )
            ]
            service._profile_manager.list_profiles = AsyncMock(return_value=expected_profiles)
            
            result = await service.list_profiles()
            
            assert result == expected_profiles
            service._profile_manager.list_profiles.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_profile_delegates(self, service):
        """Test that create_profile delegates to profile manager."""
        config = {"permitted_actions": ["OBSERVE"]}
        expected_response = AgentProfileResponse(
            success=True, profile_name="test", operation="create_profile",
            timestamp=datetime.now(timezone.utc), message="Created"
        )
        service._profile_manager.create_profile = AsyncMock(return_value=expected_response)
        
        result = await service.create_profile("test", config)
        
        assert result == expected_response
        service._profile_manager.create_profile.assert_called_once_with(
            "test", config, None, None, True
        )

    @pytest.mark.asyncio
    async def test_reload_profile_success(self, service):
        """Test successful profile reload."""
        mock_config = MagicMock()
        
        with patch('ciris_engine.services.config_manager_service.get_config') as mock_get_config:
            mock_get_config.return_value = mock_config
            await service.start()
            
            service._config_manager.reload_profile = AsyncMock()
            
            result = await service.reload_profile("test_profile")
            
            assert result.success is True
            assert result.operation == "reload_profile"
            assert "test_profile" in service._profile_manager.get_loaded_profiles()

    @pytest.mark.asyncio
    async def test_backup_config_delegates(self, service):
        """Test that backup_config delegates to backup manager."""
        expected_response = ConfigBackupResponse(
            success=True, operation="backup_config", backup_name="test_backup",
            timestamp=datetime.now(timezone.utc), files_included=["config.yaml"]
        )
        service._backup_manager.backup_config = AsyncMock(return_value=expected_response)
        
        result = await service.backup_config(backup_name="test_backup")
        
        assert result == expected_response
        service._backup_manager.backup_config.assert_called_once_with(
            True, False, "test_backup"
        )

    def test_config_history_management(self, service):
        """Test configuration change history management."""
        # Add some changes
        for i in range(150):  # More than max history
            change = {"timestamp": f"2024-01-{i:02d}", "operation": f"test_{i}"}
            service._record_config_change(change)
        
        # Should only keep last 100
        history = service.get_config_history()
        assert len(history) <= 50  # Default limit in get_config_history
        
        # Should have kept the most recent ones
        assert "test_149" in history[-1]["operation"]

    def test_get_loaded_profiles_delegates(self, service):
        """Test that get_loaded_profiles delegates to profile manager."""
        expected_profiles = ["profile1", "profile2"]
        service._profile_manager.get_loaded_profiles = MagicMock(return_value=expected_profiles)
        
        result = service.get_loaded_profiles()
        
        assert result == expected_profiles
        service._profile_manager.get_loaded_profiles.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling_in_update(self, service):
        """Test error handling in configuration updates."""
        mock_config = MagicMock()
        
        with patch('ciris_engine.services.config_manager_service.get_config') as mock_get_config:
            mock_get_config.return_value = mock_config
            await service.start()
            
            # Mock the underlying config manager to raise an error during update
            service._config_manager.update_config = MagicMock(side_effect=Exception("Database error"))
            
            # Mock get_config_value to return a value initially
            with patch.object(service, 'get_config_value', return_value={"value": "old_value"}):
                result = await service.update_config_value("test.path", "value")
                
                assert result.success is False
                assert "Database error" in result.error

    @pytest.mark.asyncio
    async def test_persist_config_change_placeholder(self, service):
        """Test placeholder persistence implementation."""
        # Should log but not fail
        await service._persist_config_change("test.path", "value", "testing")
        # No assertion needed - just ensure it doesn't raise