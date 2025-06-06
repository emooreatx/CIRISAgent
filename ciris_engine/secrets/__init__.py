"""
CIRIS Agent Secrets Management System

Provides secure detection, storage, and access control for sensitive information.
All secrets are encrypted at rest and access is audited.

Key components:
- SecretsFilter: Detects and filters secrets from content
- SecretsStore: Encrypted storage and retrieval of secrets  
- SecretsService: Main service coordinating secrets management
- SecretTools: Agent tools for managing secrets
"""

from .filter import SecretsFilter, SecretsFilterConfig, SecretPattern, DetectedSecret
from .store import SecretsStore, SecretsEncryption, SecretRecord, SecretAccessLog
from .service import SecretsService

__all__ = [
    "SecretsFilter",
    "SecretsFilterConfig", 
    "SecretPattern",
    "DetectedSecret",
    "SecretsStore",
    "SecretsEncryption",
    "SecretRecord", 
    "SecretAccessLog",
    "SecretsService",
]