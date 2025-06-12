"""Tests for the configuration validator component."""
import pytest
from unittest.mock import patch, MagicMock
from ciris_engine.runtime.config_validator import ConfigValidator
from ciris_engine.schemas.runtime_control_schemas import ConfigValidationLevel
from ciris_engine.schemas.config_schemas_v1 import AppConfig


class TestConfigValidator:
    """Test the ConfigValidator class."""

    @pytest.fixture
    def validator(self):
        """Create a validator instance."""
        return ConfigValidator()

    @pytest.mark.asyncio
    async def test_validate_complete_config_valid(self, validator):
        """Test validating a complete valid configuration."""
        # Mock AppConfig validation to pass
        with patch('ciris_engine.runtime.config_validator.AppConfig') as mock_app_config:
            mock_app_config.return_value = MagicMock()
            
            config_data = {
                "llm_services": {
                    "openai": {
                        "api_key": "test-key",
                        "model_name": "gpt-4-turbo",
                        "temperature": 0.7
                    }
                },
                "database": {
                    "db_filename": "test.db"
                }
            }
            
            result = await validator.validate_config(config_data)
            assert result.valid is True
            assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_validate_config_with_warnings(self, validator):
        """Test configuration that generates warnings."""
        # Mock AppConfig validation to pass
        with patch('ciris_engine.runtime.config_validator.AppConfig') as mock_app_config:
            mock_app_config.return_value = MagicMock()
            
            config_data = {
                "llm_services": {
                    "openai": {
                        "model_name": "gpt-4"  # Old model
                    }
                }
            }
            
            result = await validator.validate_config(config_data)
            assert result.valid is True
            assert any("GPT-4 model" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_validate_config_with_suggestions(self, validator):
        """Test configuration that generates suggestions."""
        # Mock AppConfig validation to pass
        with patch('ciris_engine.runtime.config_validator.AppConfig') as mock_app_config:
            mock_app_config.return_value = MagicMock()
            
            config_data = {
                "database": {
                    "db_filename": ""  # Empty path
                }
            }
            
            result = await validator.validate_config(config_data)
            assert result.valid is True
            assert any("custom database path" in s for s in result.suggestions)

    @pytest.mark.asyncio
    async def test_validate_config_update_timeout(self, validator):
        """Test validating timeout configuration updates."""
        # Test negative timeout
        result = await validator.validate_config_update(
            "api.timeout", -1, ConfigValidationLevel.STRICT
        )
        assert result.valid is False
        assert any("positive" in e for e in result.errors)

        # Test large timeout
        result = await validator.validate_config_update(
            "api.timeout", 400, ConfigValidationLevel.STRICT
        )
        assert result.valid is True
        assert any("user experience" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_validate_config_update_restricted_paths(self, validator):
        """Test validating updates to restricted paths."""
        result = await validator.validate_config_update(
            "llm_services.openai.api_key", 
            "new-key",
            ConfigValidationLevel.STRICT
        )
        assert result.valid is True
        assert any("environment variables" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_validate_config_update_bypass(self, validator):
        """Test bypassing validation."""
        result = await validator.validate_config_update(
            "llm_services.openai.api_key",
            "new-key", 
            ConfigValidationLevel.BYPASS
        )
        assert result.valid is True
        assert len(result.warnings) == 0

    def test_mask_sensitive_values(self, validator):
        """Test masking sensitive values in configuration."""
        config = {
            "api_key": "secret123",
            "normal_field": "visible",
            "nested": {
                "password": "hidden",
                "public": "shown"
            },
            "tokens": ["token1", "token2"]
        }
        
        masked = validator.mask_sensitive_values(config)
        assert masked["api_key"] == "***MASKED***"
        assert masked["normal_field"] == "visible"
        assert masked["nested"]["password"] == "***MASKED***"
        assert masked["nested"]["public"] == "shown"

    def test_mask_sensitive_values_with_lists(self, validator):
        """Test masking handles lists correctly."""
        config = {
            "items": [
                {"api_key": "secret", "name": "item1"},
                {"token": "hidden", "name": "item2"}
            ]
        }
        
        masked = validator.mask_sensitive_values(config)
        assert masked["items"][0]["api_key"] == "***MASKED***"
        assert masked["items"][0]["name"] == "item1"
        assert masked["items"][1]["token"] == "***MASKED***"

    @pytest.mark.asyncio
    async def test_validate_invalid_config_structure(self, validator):
        """Test validation catches invalid config structure."""
        config_data = {
            "llm_services": {
                "openai": {
                    "invalid_field": "should_fail",
                    "temperature": "not_a_number"  # Should be float
                }
            }
        }
        
        # Mock AppConfig validation to fail for invalid data
        from pydantic import ValidationError
        with patch('ciris_engine.runtime.config_validator.AppConfig', side_effect=ValidationError.from_exception_data("AppConfig", [{"type": "missing", "loc": ("field",), "msg": "Field required", "input": {}}])):
            result = await validator.validate_config(config_data)
            assert result.valid is False
            assert len(result.errors) > 0