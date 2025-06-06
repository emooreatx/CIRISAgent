"""
Schemas for CIRIS Agent Secrets Management System v1

These schemas define the data structures for secure storage, detection,
and management of sensitive information within the CIRIS pipeline.
"""

from datetime import datetime
from typing import List, Dict, Optional, Any, Literal, Tuple
from pydantic import BaseModel, Field
import uuid


class SecretPattern(BaseModel):
    """Agent-defined secret detection pattern"""
    name: str = Field(description="Pattern name")
    regex: str = Field(description="Regular expression pattern") 
    description: str = Field(description="Human-readable description")
    sensitivity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    context_hint: str = Field(description="Safe description for context")
    enabled: bool = True


class SecretRecord(BaseModel):
    """Encrypted secret storage record"""
    secret_uuid: str = Field(description="UUID identifier for the secret")
    encrypted_value: bytes = Field(description="AES-256-GCM encrypted secret value")
    encryption_key_ref: str = Field(description="Reference to encryption key in secure store")
    salt: bytes = Field(description="Cryptographic salt")
    nonce: bytes = Field(description="AES-GCM nonce")
    
    description: str = Field(description="Human-readable description")
    sensitivity_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    detected_pattern: str = Field(description="Pattern that detected this secret")
    context_hint: str = Field(description="Safe context description")
    
    created_at: datetime
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    source_message_id: Optional[str] = None
    
    auto_decapsulate_for_actions: List[str] = Field(default_factory=list)
    manual_access_only: bool = False


class SecretsFilter(BaseModel):
    """Agent-configurable secrets detection rules"""
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


class SecretReference(BaseModel):
    """Non-sensitive reference to a stored secret for SystemSnapshot"""
    uuid: str
    description: str
    context_hint: str
    sensitivity: str
    auto_decapsulate_actions: List[str]
    created_at: datetime
    last_accessed: Optional[datetime]


class SecretAccessLog(BaseModel):
    """Audit log for secret access"""
    access_id: str = Field(description="Unique access identifier")
    secret_uuid: str = Field(description="Secret that was accessed")
    access_type: Literal["VIEW", "DECRYPT", "UPDATE", "DELETE"]
    accessor: str = Field(description="Who/what accessed the secret")
    purpose: str = Field(description="Stated purpose for access")
    timestamp: datetime
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    action_context: Optional[str] = None
    success: bool = True
    failure_reason: Optional[str] = None


class DetectedSecret(BaseModel):
    """Secret detected during filtering process"""
    original_value: str = Field(description="Original secret value")
    secret_uuid: str = Field(description="Generated UUID for this secret")
    pattern_name: str = Field(description="Detection pattern that found this secret")
    description: str = Field(description="Human-readable description")
    sensitivity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    context_hint: str = Field(description="Safe context description")
    replacement_text: str = Field(description="Text to replace secret with in context")


class SecretsFilterResult(BaseModel):
    """Result of applying secrets filter to content"""
    filtered_content: str = Field(description="Content with secrets replaced by references")
    detected_secrets: List[DetectedSecret] = Field(default_factory=list)
    secrets_found: int = Field(default=0)
    patterns_matched: List[str] = Field(default_factory=list)


# Action Parameters for Secret Tools

class RecallSecretParams(BaseModel):
    """Parameters for RECALL_SECRET tool"""
    secret_uuid: str = Field(description="UUID of the secret to recall")
    purpose: str = Field(description="Why the secret is needed (for audit)")
    decrypt: bool = Field(default=False, description="Whether to decrypt the secret value")


class UpdateSecretsFilterParams(BaseModel):
    """Parameters for UPDATE_SECRETS_FILTER tool"""
    operation: Literal["add_pattern", "remove_pattern", "update_pattern", "get_current"]
    
    # For add_pattern/update_pattern
    pattern: Optional[SecretPattern] = None
    
    # For remove_pattern  
    pattern_name: Optional[str] = None
    
    # For configuration changes
    config_updates: Optional[Dict[str, Any]] = None


# Built-in Secret Patterns

BUILTIN_SECRET_PATTERNS = [
    SecretPattern(
        name="api_keys",
        regex=r"(?i)api[_-]?key[s]?[\s:=]+['\"]?([a-z0-9]{20,})['\"]?",
        description="API Key",
        sensitivity="HIGH",
        context_hint="API authentication key"
    ),
    SecretPattern(
        name="bearer_tokens",
        regex=r"(?i)bearer[\s]+([a-z0-9\-_.]{20,})",
        description="Bearer Token",
        sensitivity="HIGH", 
        context_hint="Bearer authentication token"
    ),
    SecretPattern(
        name="passwords",
        regex=r"(?i)password[s]?[\s:=]+['\"]?([^\s'\"]{8,})['\"]?",
        description="Password",
        sensitivity="CRITICAL",
        context_hint="Password credential"
    ),
    SecretPattern(
        name="urls_with_auth",
        regex=r"https?://[^:]+:[^@]+@[^\s]+",
        description="URL with Authentication",
        sensitivity="HIGH",
        context_hint="Authenticated URL"
    ),
    SecretPattern(
        name="private_keys",
        regex=r"-----BEGIN [A-Z ]+PRIVATE KEY-----",
        description="Private Key",
        sensitivity="CRITICAL",
        context_hint="Cryptographic private key"
    ),
    SecretPattern(
        name="credit_cards",
        regex=r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b",
        description="Credit Card Number",
        sensitivity="CRITICAL",
        context_hint="Payment card number"
    ),
    SecretPattern(
        name="social_security",
        regex=r"\b\d{3}-\d{2}-\d{4}\b",
        description="Social Security Number",
        sensitivity="CRITICAL",
        context_hint="Social Security Number"
    ),
    SecretPattern(
        name="aws_access_key",
        regex=r"AKIA[0-9A-Z]{16}",
        description="AWS Access Key",
        sensitivity="HIGH",
        context_hint="AWS access key"
    ),
    SecretPattern(
        name="aws_secret_key",
        regex=r"(?i)aws[_-]?secret[_-]?access[_-]?key[\s:=]+['\"]?([a-z0-9/+=]{40})['\"]?",
        description="AWS Secret Key",
        sensitivity="CRITICAL",
        context_hint="AWS secret access key"
    ),
    SecretPattern(
        name="github_token",
        regex=r"gh[ps]_[a-zA-Z0-9]{36}",
        description="GitHub Token",
        sensitivity="HIGH",
        context_hint="GitHub access token"
    ),
    SecretPattern(
        name="slack_token",
        regex=r"xox[baprs]-([0-9a-zA-Z]{10,48})",
        description="Slack Token",
        sensitivity="HIGH",
        context_hint="Slack API token"
    ),
    SecretPattern(
        name="discord_token",
        regex=r"[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}",
        description="Discord Bot Token",
        sensitivity="HIGH",
        context_hint="Discord bot token"
    ),
]