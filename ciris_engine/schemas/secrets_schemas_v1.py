"""
Schemas for CIRIS Agent Secrets Management System v1

These schemas define the data structures for secure storage, detection,
and management of sensitive information within the CIRIS pipeline.
"""

from datetime import datetime
from typing import List, Dict, Optional, Any, Literal, TYPE_CHECKING
from pydantic import BaseModel, Field
from enum import Enum
from .foundational_schemas_v1 import SensitivityLevel

if TYPE_CHECKING:
    from .config_schemas_v1 import SecretPattern


class SecretType(str, Enum):
    """Standard secret types with default detection patterns"""
    API_KEYS = "api_keys"
    BEARER_TOKENS = "bearer_tokens" 
    PASSWORDS = "passwords"
    URLS_WITH_AUTH = "urls_with_auth"
    PRIVATE_KEYS = "private_keys"
    CREDIT_CARDS = "credit_cards"
    SOCIAL_SECURITY = "social_security"
    AWS_ACCESS_KEY = "aws_access_key"
    AWS_SECRET_KEY = "aws_secret_key"
    GITHUB_TOKEN = "github_token"
    SLACK_TOKEN = "slack_token"
    DISCORD_TOKEN = "discord_token"




class SecretRecord(BaseModel):
    """Encrypted secret storage record"""
    secret_uuid: str = Field(description="UUID identifier for the secret")
    encrypted_value: bytes = Field(description="AES-256-GCM encrypted secret value")
    encryption_key_ref: str = Field(description="Reference to encryption key in secure store")
    salt: bytes = Field(description="Cryptographic salt")
    nonce: bytes = Field(description="AES-GCM nonce")
    
    description: str = Field(description="Human-readable description")
    sensitivity_level: SensitivityLevel
    detected_pattern: str = Field(description="Pattern that detected this secret")
    context_hint: str = Field(description="Safe context description")
    
    created_at: datetime
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    source_message_id: Optional[str] = None
    
    auto_decapsulate_for_actions: List[str] = Field(default_factory=list)
    manual_access_only: bool = False




class SecretReference(BaseModel):
    """Non-sensitive reference to a stored secret for SystemSnapshot"""
    uuid: str
    description: str
    context_hint: str
    sensitivity: str
    detected_pattern: str
    auto_decapsulate_actions: List[str]
    created_at: datetime
    last_accessed: Optional[datetime]


class SecretAccessLog(BaseModel):
    """Audit log for secret access"""
    access_id: str = Field(description="Unique access identifier")
    secret_uuid: str = Field(description="Secret that was accessed")
    access_type: Literal["VIEW", "DECRYPT", "UPDATE", "DELETE", "STORE"]
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
    sensitivity: SensitivityLevel
    context_hint: str = Field(description="Safe context description")
    replacement_text: str = Field(description="Text to replace secret with in context")


class SecretsFilterResult(BaseModel):
    """Result of applying secrets filter to content"""
    filtered_content: str = Field(description="Content with secrets replaced by references")
    detected_secrets: List[DetectedSecret] = Field(default_factory=list)
    secrets_found: int = Field(default=0)
    patterns_matched: List[str] = Field(default_factory=list)



class RecallSecretParams(BaseModel):
    """Parameters for RECALL_SECRET tool"""
    secret_uuid: str = Field(description="UUID of the secret to recall")
    purpose: str = Field(description="Why the secret is needed (for audit)")
    decrypt: bool = Field(default=False, description="Whether to decrypt the secret value")


class UpdateSecretsFilterParams(BaseModel):
    """Parameters for UPDATE_SECRETS_FILTER tool"""
    operation: Literal["add_pattern", "remove_pattern", "update_pattern", "get_current"]
    
    pattern: Optional["SecretPattern"] = None
    
    pattern_name: Optional[str] = None
    
    config_updates: Optional[Dict[str, Any]] = None


