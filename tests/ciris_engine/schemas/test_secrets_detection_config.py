"""
Tests for secrets detection configuration in config schemas
"""

import pytest
from ciris_engine.schemas.config_schemas_v1 import (
    SecretsDetectionConfig, 
    SecretPattern,
    SecretsConfig
)
from ciris_engine.schemas.foundational_schemas_v1 import SensitivityLevel


class TestSecretsDetectionConfig:
    """Test secrets detection configuration functionality"""
    
    def test_default_patterns_loaded(self):
        """Test that default patterns are properly loaded"""
        config = SecretsDetectionConfig()
        
        # Should have default patterns
        assert len(config.default_patterns) > 0
        
        # Check specific patterns exist
        pattern_names = [p.name for p in config.default_patterns]
        expected_patterns = [
            "api_keys", "bearer_tokens", "passwords", "urls_with_auth",
            "private_keys", "credit_cards", "social_security", 
            "aws_access_key", "aws_secret_key", "github_token",
            "slack_token", "discord_token"
        ]
        
        for expected in expected_patterns:
            assert expected in pattern_names, f"Missing pattern: {expected}"
    
    def test_pattern_structure(self):
        """Test that patterns have correct structure"""
        config = SecretsDetectionConfig()
        
        for pattern in config.default_patterns:
            assert isinstance(pattern.name, str)
            assert isinstance(pattern.regex, str)
            assert isinstance(pattern.description, str)
            assert isinstance(pattern.sensitivity, SensitivityLevel)
            assert isinstance(pattern.context_hint, str)
            assert isinstance(pattern.enabled, bool)
            
            # Regex should be non-empty
            assert len(pattern.regex) > 0
            
            # Description should be non-empty
            assert len(pattern.description) > 0
    
    def test_custom_patterns_functionality(self):
        """Test adding custom patterns"""
        config = SecretsDetectionConfig()
        
        # Add a custom pattern
        custom_pattern = SecretPattern(
            name="test_token",
            regex=r"test_[a-f0-9]{32}",
            description="Test Token",
            sensitivity=SensitivityLevel.MEDIUM,
            context_hint="Test authentication token"
        )
        
        config.custom_patterns.append(custom_pattern)
        
        # Verify it was added
        assert len(config.custom_patterns) == 1
        assert config.custom_patterns[0].name == "test_token"
        assert config.custom_patterns[0].sensitivity == SensitivityLevel.MEDIUM
    
    def test_disabled_patterns_functionality(self):
        """Test disabling patterns"""
        config = SecretsDetectionConfig()
        
        # Disable a pattern
        config.disabled_patterns.append("credit_cards")
        
        # Verify it's in the disabled list
        assert "credit_cards" in config.disabled_patterns
        
        # Default patterns should still exist
        pattern_names = [p.name for p in config.default_patterns]
        assert "credit_cards" in pattern_names
    
    def test_sensitivity_levels(self):
        """Test that patterns use appropriate sensitivity levels"""
        config = SecretsDetectionConfig()
        
        # Check that critical patterns are marked appropriately
        critical_patterns = [p for p in config.default_patterns 
                           if p.sensitivity == SensitivityLevel.CRITICAL]
        critical_names = [p.name for p in critical_patterns]
        
        # These should be critical
        assert "passwords" in critical_names
        assert "private_keys" in critical_names
        assert "credit_cards" in critical_names
        assert "social_security" in critical_names
        assert "aws_secret_key" in critical_names
        
        # Check that high patterns exist
        high_patterns = [p for p in config.default_patterns 
                        if p.sensitivity == SensitivityLevel.HIGH]
        high_names = [p.name for p in high_patterns]
        
        assert "api_keys" in high_names
        assert "bearer_tokens" in high_names
        assert "urls_with_auth" in high_names
    
    def test_pattern_regex_compilation(self):
        """Test that all regex patterns compile successfully"""
        import re
        
        config = SecretsDetectionConfig()
        
        for pattern in config.default_patterns:
            try:
                compiled_regex = re.compile(pattern.regex)
                assert compiled_regex is not None
            except re.error as e:
                pytest.fail(f"Pattern '{pattern.name}' has invalid regex: {pattern.regex}, error: {e}")
    
    def test_secrets_config_integration(self):
        """Test that SecretsDetectionConfig integrates properly with SecretsConfig"""
        secrets_config = SecretsConfig()
        
        # Should have detection config
        assert hasattr(secrets_config, 'detection')
        assert isinstance(secrets_config.detection, SecretsDetectionConfig)
        
        # Should have default patterns
        assert len(secrets_config.detection.default_patterns) > 0
        
        # Should be enabled by default
        assert secrets_config.detection.builtin_patterns is True
        assert secrets_config.detection.custom_patterns_enabled is True
    
    def test_agent_pattern_management(self):
        """Test agent's ability to manage patterns dynamically"""
        config = SecretsDetectionConfig()
        
        # Initial state
        initial_pattern_count = len(config.default_patterns)
        assert len(config.custom_patterns) == 0
        assert len(config.disabled_patterns) == 0
        
        # Agent adds a custom pattern
        new_pattern = SecretPattern(
            name="custom_api_key",
            regex=r"cust_[a-zA-Z0-9]{24}",
            description="Custom API Key",
            sensitivity=SensitivityLevel.HIGH,
            context_hint="Custom service API key"
        )
        config.custom_patterns.append(new_pattern)
        
        # Agent disables a default pattern
        config.disabled_patterns.append("social_security")
        
        # Verify changes
        assert len(config.custom_patterns) == 1
        assert len(config.disabled_patterns) == 1
        assert len(config.default_patterns) == initial_pattern_count  # Default patterns unchanged
        
        # Total effective patterns would be: default + custom - disabled
        effective_patterns = [p for p in config.default_patterns if p.name not in config.disabled_patterns]
        effective_patterns.extend(config.custom_patterns)
        
        assert len(effective_patterns) == initial_pattern_count  # Added 1, disabled 1
    
    def test_configuration_persistence(self):
        """Test that configuration can be serialized and deserialized"""
        original_config = SecretsDetectionConfig()
        
        # Add custom pattern and disable one
        custom_pattern = SecretPattern(
            name="test_pattern",
            regex=r"TEST_[0-9]{8}",
            description="Test Pattern",
            sensitivity=SensitivityLevel.LOW,
            context_hint="Test identifier"
        )
        original_config.custom_patterns.append(custom_pattern)
        original_config.disabled_patterns.append("discord_token")
        
        # Serialize to dict
        config_dict = original_config.model_dump()
        
        # Recreate from dict
        restored_config = SecretsDetectionConfig.model_validate(config_dict)
        
        # Verify everything was preserved
        assert len(restored_config.default_patterns) == len(original_config.default_patterns)
        assert len(restored_config.custom_patterns) == 1
        assert restored_config.custom_patterns[0].name == "test_pattern"
        assert "discord_token" in restored_config.disabled_patterns
        assert restored_config.sensitivity_threshold == original_config.sensitivity_threshold