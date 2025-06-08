"""
Secrets Detection and Filtering System for CIRIS Agent.

Automatically detects and protects sensitive information while maintaining
the agent's ability to reason about and use secrets safely.
"""
import re
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Literal, Any, cast
from dataclasses import dataclass
from pydantic import BaseModel, Field
from ..schemas.foundational_schemas_v1 import SensitivityLevel

from ..protocols.secrets_interface import SecretsFilterInterface
from ..schemas.secrets_schemas_v1 import (
    SecretPattern as SchemaSecretPattern,
    SecretsFilter as SchemaSecretsFilter,
    DetectedSecret,
    SecretsFilterResult
)
from ..schemas.config_schemas_v1 import SecretsDetectionConfig, SecretPattern as ConfigSecretPattern

logger = logging.getLogger(__name__)






class SecretsFilter(SecretsFilterInterface):
    """
    Automatic secrets detection and filtering system.
    
    Detects secrets in text and replaces them with secure UUID references
    while maintaining context for the agent.
    """
    
    def __init__(self, detection_config: Optional[SecretsDetectionConfig] = None) -> None:
        self.detection_config = detection_config or SecretsDetectionConfig()
        self._compiled_patterns: Dict[str, re.Pattern] = {}
        self._compile_patterns()
        
    def _compile_patterns(self) -> None:
        """Compile all active patterns for efficient matching."""
        self._compiled_patterns.clear()
        
        # Add default (builtin) patterns if enabled
        if self.detection_config.builtin_patterns:
            for pattern in self.detection_config.default_patterns:
                if pattern.enabled and pattern.name not in self.detection_config.disabled_patterns:
                    try:
                        self._compiled_patterns[pattern.name] = re.compile(pattern.regex)
                    except re.error as e:
                        logger.error(f"Failed to compile default pattern {pattern.name}: {e}")
                        
        # Add custom patterns from config
        for pattern in self.detection_config.custom_patterns:
            if pattern.enabled and pattern.name not in self.detection_config.disabled_patterns:
                try:
                    self._compiled_patterns[pattern.name] = re.compile(pattern.regex)
                except re.error as e:
                    logger.error(f"Failed to compile custom pattern {pattern.name}: {e}")
                    
    def detect_secrets(self, text: str, context_hint: str = "") -> List[DetectedSecret]:
        """
        Detect secrets in the given text.
        
        Args:
            text: Text to scan for secrets
            context_hint: Safe context description for logging
            
        Returns:
            List of detected secrets with metadata
        """
        detected_secrets = []
        
        for pattern_name, compiled_pattern in self._compiled_patterns.items():
            try:
                matches = compiled_pattern.finditer(text)
                for match in matches:
                    # Get pattern metadata
                    pattern_info = self._get_pattern_info(pattern_name)
                    if not pattern_info:
                        continue
                        
                    # Generate UUID for this secret
                    secret_uuid = str(uuid.uuid4())
                    
                    # Create replacement text
                    replacement_text = f"{{SECRET:{secret_uuid}:{pattern_info.description}}}"
                    
                    # Create detected secret record
                    detected_secret = DetectedSecret(
                        secret_uuid=secret_uuid,
                        original_value=match.group(0),
                        replacement_text=replacement_text,
                        pattern_name=pattern_name,
                        description=pattern_info.description,
                        sensitivity=pattern_info.sensitivity,  # Use pattern sensitivity directly
                        context_hint=context_hint
                    )
                    
                    detected_secrets.append(detected_secret)
                    
            except Exception as e:
                logger.error(f"Error processing pattern {pattern_name}: {e}")
                
        return detected_secrets
        
    def filter_text(self, text: str, context_hint: str = "") -> Tuple[str, List[DetectedSecret]]:
        """
        Filter text by detecting and replacing secrets with UUID references.
        
        Args:
            text: Original text containing potential secrets
            context_hint: Safe context description for logging
            
        Returns:
            Tuple of (filtered_text, detected_secrets_list)
        """
        detected_secrets = self.detect_secrets(text, context_hint)
        
        if not detected_secrets:
            return text, []
            
        # Replace secrets with UUID references using simple string replacement
        filtered_text = text
        for secret in detected_secrets:
            filtered_text = filtered_text.replace(secret.original_value, secret.replacement_text)
            
        logger.info(
            f"Filtered {len(detected_secrets)} secrets from text. Context: {context_hint}"
        )
        
        return filtered_text, detected_secrets
        
    def _get_pattern_info(self, pattern_name: str) -> Optional[ConfigSecretPattern]:
        """Get pattern information by name."""
        # Check custom patterns first
        for pattern in self.detection_config.custom_patterns:
            if pattern.name == pattern_name:
                return pattern
                
        # Check default patterns
        for pattern in self.detection_config.default_patterns:
            if pattern.name == pattern_name:
                return pattern
                
        return None
        
    def add_custom_pattern(self, pattern: ConfigSecretPattern) -> None:
        """Add a new custom pattern."""
        # Remove existing pattern with same name
        self.detection_config.custom_patterns = [
            p for p in self.detection_config.custom_patterns if p.name != pattern.name
        ]
        self.detection_config.custom_patterns.append(pattern)
        self._compile_patterns()
        
        logger.info(f"Added custom secret pattern: {pattern.name}")
        
    def remove_custom_pattern(self, pattern_name: str) -> bool:
        """Remove a custom pattern by name."""
        original_count = len(self.detection_config.custom_patterns)
        self.detection_config.custom_patterns = [
            p for p in self.detection_config.custom_patterns if p.name != pattern_name
        ]
        
        if len(self.detection_config.custom_patterns) < original_count:
            self._compile_patterns()
            logger.info(f"Removed custom secret pattern: {pattern_name}")
            return True
        return False
        
    def disable_pattern(self, pattern_name: str) -> None:
        """Disable a pattern (default or custom)."""
        if pattern_name not in self.detection_config.disabled_patterns:
            self.detection_config.disabled_patterns.append(pattern_name)
            self._compile_patterns()
            logger.info(f"Disabled secret pattern: {pattern_name}")
            
    def enable_pattern(self, pattern_name: str) -> None:
        """Re-enable a previously disabled pattern."""
        if pattern_name in self.detection_config.disabled_patterns:
            self.detection_config.disabled_patterns.remove(pattern_name)
            self._compile_patterns()
            logger.info(f"Enabled secret pattern: {pattern_name}")
        
    def get_pattern_stats(self) -> Dict[str, Any]:
        """Get statistics about active patterns."""
        default_active = len([p for p in self.detection_config.default_patterns 
                            if p.enabled and p.name not in self.detection_config.disabled_patterns])
        return {
            "total_patterns": len(self._compiled_patterns),
            "default_patterns": default_active,
            "custom_patterns": len([p for p in self.detection_config.custom_patterns if p.enabled]),
            "disabled_patterns": len(self.detection_config.disabled_patterns),
            "builtin_patterns": self.detection_config.builtin_patterns,
            "filter_version": "v1.0"
        }
        
    def export_config(self) -> Dict[str, Any]:
        """Export current configuration for persistence."""
        return self.detection_config.model_dump()
        
    def import_config(self, config_dict: Dict[str, Any]) -> None:
        """Import configuration from dictionary."""
        self.detection_config = SecretsDetectionConfig(**config_dict)
        self._compile_patterns()
        logger.info(f"Imported secrets detection config")
    
    # Implement SecretsFilterInterface methods
    async def filter_content(self, content: str, source_id: Optional[str] = None) -> SecretsFilterResult:
        """Filter content for secrets using the text filtering method."""
        # Return a simple result for interface compatibility
        filtered_text, detected_secrets = self.filter_text(content)
        
        # Convert local DetectedSecret to schema format
        schema_secrets = []
        for secret in detected_secrets:
            schema_secret = DetectedSecret(
                original_value=secret.original_value,
                secret_uuid=secret.secret_uuid,
                pattern_name=secret.pattern_name,
                description=secret.description,
                sensitivity=secret.sensitivity,
                context_hint=secret.context_hint,
                replacement_text=secret.replacement_text
            )
            schema_secrets.append(schema_secret)
        
        return SecretsFilterResult(
            filtered_content=filtered_text,
            detected_secrets=schema_secrets,
            secrets_found=len(detected_secrets),
            patterns_matched=[s.pattern_name for s in detected_secrets]
        )
    
    async def add_pattern(self, pattern: SchemaSecretPattern) -> bool:
        """Add a new secret detection pattern."""
        try:
            # Convert to config SecretPattern format
            config_pattern = ConfigSecretPattern(
                name=pattern.name,
                regex=pattern.regex,
                description=pattern.description,
                sensitivity=pattern.sensitivity,
                context_hint=pattern.context_hint,
                enabled=pattern.enabled
            )
            self.add_custom_pattern(config_pattern)
            return True
        except Exception:
            return False
    
    async def remove_pattern(self, pattern_name: str) -> bool:
        """Remove a secret detection pattern."""
        return self.remove_custom_pattern(pattern_name)
    
    async def get_filter_config(self) -> SchemaSecretsFilter:
        """Get the current filter configuration."""
        # Convert detection config to schema format
        return SchemaSecretsFilter(
            filter_id="config_based",
            version=1,
            builtin_patterns_enabled=self.detection_config.builtin_patterns,
            custom_patterns=[
                SchemaSecretPattern(
                    name=p.name,
                    regex=p.regex,
                    description=p.description,
                    sensitivity=p.sensitivity,
                    context_hint=p.context_hint,
                    enabled=p.enabled
                ) for p in self.detection_config.custom_patterns
            ],
            disabled_patterns=self.detection_config.disabled_patterns,
            sensitivity_overrides={},  # Not used in new system
            require_confirmation_for=["CRITICAL"],  # Default
            auto_decrypt_for_actions=["speak", "tool"]  # Default
        )
    
    async def update_filter_config(self, updates: Dict[str, Any]) -> bool:
        """Update filter configuration settings."""
        try:
            # Update detection config based on provided updates
            for key, value in updates.items():
                if hasattr(self.detection_config, key):
                    setattr(self.detection_config, key, value)
            # Recompile patterns after updates
            self._compile_patterns()
            return True
        except Exception:
            return False