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
    DetectedSecret as SchemaDetectedSecret,
    SecretsFilterResult
)

logger = logging.getLogger(__name__)


class SecretPattern(BaseModel):
    """Agent-defined secret detection pattern."""
    name: str = Field(description="Pattern name")
    regex: str = Field(description="Regular expression pattern")
    description: str = Field(description="Human-readable description")
    sensitivity: SensitivityLevel
    enabled: bool = True


class SecretsFilterConfig(BaseModel):
    """Agent-configurable secrets detection rules."""
    filter_id: str = Field(description="Unique identifier for this filter set")
    version: int = Field(description="Version number for updates")
    
    # Built-in patterns (always active)
    builtin_patterns_enabled: bool = True
    
    # Agent-defined custom patterns
    custom_patterns: List[SecretPattern] = Field(default_factory=list)
    
    # Pattern overrides
    disabled_patterns: List[str] = Field(default_factory=list)
    sensitivity_overrides: Dict[str, str] = Field(default_factory=dict)
    
    # Behavioral settings
    require_confirmation_for: List[str] = Field(default=["CRITICAL"])
    auto_decrypt_for_actions: List[str] = Field(default=["speak", "tool"])


@dataclass
class DetectedSecret:
    """Information about a detected secret."""
    secret_uuid: str
    original_text: str
    replacement_text: str
    pattern_name: str
    description: str
    sensitivity: SensitivityLevel
    context_hint: str
    start_pos: int
    end_pos: int


class SecretsFilter(SecretsFilterInterface):
    """
    Automatic secrets detection and filtering system.
    
    Detects secrets in text and replaces them with secure UUID references
    while maintaining context for the agent.
    """
    
    def __init__(self, config: Optional[SecretsFilterConfig] = None) -> None:
        self.config = config or SecretsFilterConfig(
            filter_id="default",
            version=1
        )
        self._builtin_patterns = self._load_builtin_patterns()
        self._compiled_patterns: Dict[str, re.Pattern] = {}
        self._compile_patterns()
        
    def _load_builtin_patterns(self) -> Dict[str, SecretPattern]:
        """Load built-in secret detection patterns."""
        return {
            "api_key": SecretPattern(
                name="api_key",
                regex=r"(?i)api[_-]?key[s]?[\s:=]+['\"]?[a-z0-9_-]{15,}['\"]?",
                description="API Key",
                sensitivity=SensitivityLevel.HIGH
            ),
            "bearer_token": SecretPattern(
                name="bearer_token", 
                regex=r"(?i)bearer[_-]?token[s]?[\s:=]+['\"]?[a-z0-9\-_.]{20,}['\"]?",
                description="Bearer Token",
                sensitivity=SensitivityLevel.HIGH
            ),
            "password": SecretPattern(
                name="password",
                regex=r"(?i)password[s]?[\s:=]+['\"]?[^\s'\"]{8,}['\"]?",
                description="Password",
                sensitivity=SensitivityLevel.CRITICAL
            ),
            "url_with_auth": SecretPattern(
                name="url_with_auth",
                regex=r"https?://[^:]+:[^@]+@[^\s]+",
                description="URL with Authentication", 
                sensitivity=SensitivityLevel.HIGH
            ),
            "private_key": SecretPattern(
                name="private_key",
                regex=r"-----BEGIN [A-Z ]+PRIVATE KEY-----",
                description="Private Key",
                sensitivity=SensitivityLevel.CRITICAL
            ),
            "credit_card": SecretPattern(
                name="credit_card",
                regex=r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b",
                description="Credit Card Number",
                sensitivity=SensitivityLevel.CRITICAL
            ),
            "social_security": SecretPattern(
                name="social_security",
                regex=r"\b\d{3}-\d{2}-\d{4}\b",
                description="Social Security Number",
                sensitivity=SensitivityLevel.CRITICAL
            ),
            "aws_access_key": SecretPattern(
                name="aws_access_key",
                regex=r"(?i)(?:AKIA|ASIA)[0-9A-Z]{16}",
                description="AWS Access Key ID",
                sensitivity=SensitivityLevel.HIGH
            ),
            "aws_secret_key": SecretPattern(
                name="aws_secret_key", 
                regex=r"(?i)aws[_-]?secret[_-]?access[_-]?key[s]?[\s:=]+['\"]?[a-z0-9/+=]{40}['\"]?",
                description="AWS Secret Access Key",
                sensitivity=SensitivityLevel.CRITICAL
            ),
            "github_token": SecretPattern(
                name="github_token",
                regex=r"(?i)github[_-]?token[s]?[\s:=]+['\"]?ghp_[a-z0-9]{36}['\"]?",
                description="GitHub Personal Access Token",
                sensitivity=SensitivityLevel.HIGH
            ),
            "slack_token": SecretPattern(
                name="slack_token",
                regex=r"(?i)xox[bpars]-[0-9]{12}-[0-9]{12}-[a-z0-9]{24}",
                description="Slack Token",
                sensitivity=SensitivityLevel.HIGH
            ),
            "discord_token": SecretPattern(
                name="discord_token",
                regex=r"(?i)discord[_-]?token[s]?[\s:=]+['\"]?[a-z0-9]{50,}['\"]?",
                description="Discord Bot Token",
                sensitivity=SensitivityLevel.HIGH
            )
        }
        
    def _compile_patterns(self) -> None:
        """Compile all active patterns for efficient matching."""
        self._compiled_patterns.clear()
        
        # Add builtin patterns if enabled
        if self.config.builtin_patterns_enabled:
            for name, pattern in self._builtin_patterns.items():
                if name not in self.config.disabled_patterns:
                    try:
                        self._compiled_patterns[name] = re.compile(pattern.regex)
                    except re.error as e:
                        logger.error(f"Failed to compile builtin pattern {name}: {e}")
                        
        # Add custom patterns
        for pattern in self.config.custom_patterns:
            if pattern.enabled and pattern.name not in self.config.disabled_patterns:
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
                        original_text=match.group(0),
                        replacement_text=replacement_text,
                        pattern_name=pattern_name,
                        description=pattern_info.description,
                        sensitivity=self._get_effective_sensitivity(pattern_name, pattern_info.sensitivity),
                        context_hint=context_hint,
                        start_pos=match.start(),
                        end_pos=match.end()
                    )
                    
                    detected_secrets.append(detected_secret)
                    
            except Exception as e:
                logger.error(f"Error processing pattern {pattern_name}: {e}")
                
        # Sort by position (reverse order for replacement)
        detected_secrets.sort(key=lambda x: x.start_pos, reverse=True)
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
            
        # Replace secrets with UUID references (in reverse order to maintain positions)
        filtered_text = text
        for secret in detected_secrets:
            filtered_text = (
                filtered_text[:secret.start_pos] + 
                secret.replacement_text + 
                filtered_text[secret.end_pos:]
            )
            
        logger.info(
            f"Filtered {len(detected_secrets)} secrets from text. Context: {context_hint}"
        )
        
        return filtered_text, detected_secrets
        
    def _get_pattern_info(self, pattern_name: str) -> Optional[SecretPattern]:
        """Get pattern information by name."""
        # Check custom patterns first
        for pattern in self.config.custom_patterns:
            if pattern.name == pattern_name:
                return pattern
                
        # Check builtin patterns
        return self._builtin_patterns.get(pattern_name)
        
    def _get_effective_sensitivity(self, pattern_name: str, default_sensitivity: str) -> str:
        """Get effective sensitivity level including overrides."""
        return self.config.sensitivity_overrides.get(pattern_name, default_sensitivity)
        
    def add_custom_pattern(self, pattern: SecretPattern) -> None:
        """Add a new custom pattern."""
        # Remove existing pattern with same name
        self.config.custom_patterns = [
            p for p in self.config.custom_patterns if p.name != pattern.name
        ]
        self.config.custom_patterns.append(pattern)
        self.config.version += 1
        self._compile_patterns()
        
        logger.info(f"Added custom secret pattern: {pattern.name}")
        
    def remove_custom_pattern(self, pattern_name: str) -> bool:
        """Remove a custom pattern by name."""
        original_count = len(self.config.custom_patterns)
        self.config.custom_patterns = [
            p for p in self.config.custom_patterns if p.name != pattern_name
        ]
        
        if len(self.config.custom_patterns) < original_count:
            self.config.version += 1
            self._compile_patterns()
            logger.info(f"Removed custom secret pattern: {pattern_name}")
            return True
        return False
        
    def disable_pattern(self, pattern_name: str) -> None:
        """Disable a pattern (builtin or custom)."""
        if pattern_name not in self.config.disabled_patterns:
            self.config.disabled_patterns.append(pattern_name)
            self.config.version += 1
            self._compile_patterns()
            logger.info(f"Disabled secret pattern: {pattern_name}")
            
    def enable_pattern(self, pattern_name: str) -> None:
        """Re-enable a previously disabled pattern."""
        if pattern_name in self.config.disabled_patterns:
            self.config.disabled_patterns.remove(pattern_name)
            self.config.version += 1
            self._compile_patterns()
            logger.info(f"Enabled secret pattern: {pattern_name}")
            
    def set_sensitivity_override(self, pattern_name: str, sensitivity: str) -> None:
        """Override the sensitivity level for a pattern."""
        valid_levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        if sensitivity not in valid_levels:
            raise ValueError(f"Invalid sensitivity level. Must be one of: {valid_levels}")
            
        self.config.sensitivity_overrides[pattern_name] = sensitivity
        self.config.version += 1
        logger.info(f"Set sensitivity override for {pattern_name}: {sensitivity}")
        
    def get_pattern_stats(self) -> Dict[str, Any]:
        """Get statistics about active patterns."""
        return {
            "total_patterns": len(self._compiled_patterns),
            "builtin_patterns": len([p for p in self._builtin_patterns.keys() 
                                  if p in self._compiled_patterns]),
            "custom_patterns": len(self.config.custom_patterns),
            "disabled_patterns": len(self.config.disabled_patterns),
            "sensitivity_overrides": len(self.config.sensitivity_overrides),
            "filter_version": self.config.version
        }
        
    def export_config(self) -> Dict[str, Any]:
        """Export current configuration for persistence."""
        return self.config.model_dump()
        
    def import_config(self, config_dict: Dict[str, Any]) -> None:
        """Import configuration from dictionary."""
        self.config = SecretsFilterConfig(**config_dict)
        self._compile_patterns()
        logger.info(f"Imported secrets filter config version {self.config.version}")
    
    # Implement SecretsFilterInterface methods
    async def filter_content(self, content: str, source_id: Optional[str] = None) -> SecretsFilterResult:
        """Filter content for secrets using the text filtering method."""
        # Return a simple result for interface compatibility
        filtered_text, detected_secrets = self.filter_text(content)
        
        # Convert local DetectedSecret to schema format
        schema_secrets = []
        for secret in detected_secrets:
            schema_secret = SchemaDetectedSecret(
                original_value=secret.original_text,
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
            # Convert to local SecretPattern format
            local_pattern = SecretPattern(
                name=pattern.name,
                regex=pattern.regex,
                description=pattern.description,
                sensitivity=pattern.sensitivity,
                enabled=True
            )
            self.add_custom_pattern(local_pattern)
            return True
        except Exception:
            return False
    
    async def remove_pattern(self, pattern_name: str) -> bool:
        """Remove a secret detection pattern."""
        return self.remove_custom_pattern(pattern_name)
    
    async def get_filter_config(self) -> SchemaSecretsFilter:
        """Get the current filter configuration."""
        # Convert local config to schema format
        return SchemaSecretsFilter(
            filter_id=self.config.filter_id,
            version=self.config.version,
            builtin_patterns_enabled=self.config.builtin_patterns_enabled,
            custom_patterns=[
                SchemaSecretPattern(
                    name=p.name,
                    regex=p.regex,
                    description=p.description,
                    sensitivity=p.sensitivity,
                    context_hint=p.description,  # Use description as context hint
                    enabled=p.enabled
                ) for p in self.config.custom_patterns
            ],
            disabled_patterns=self.config.disabled_patterns,
            sensitivity_overrides=self.config.sensitivity_overrides,
            require_confirmation_for=self.config.require_confirmation_for,
            auto_decrypt_for_actions=self.config.auto_decrypt_for_actions
        )
    
    async def update_filter_config(self, updates: Dict[str, Any]) -> bool:
        """Update filter configuration settings."""
        try:
            # Simple update - could be made more sophisticated
            for key, value in updates.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
            # Recompile patterns if patterns were updated
            self._compile_patterns()
            return True
        except Exception:
            return False