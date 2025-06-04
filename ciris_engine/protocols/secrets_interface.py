"""
Secrets Management Interface Protocols

Defines the contracts for secure secrets detection, storage, and access control
within the CIRIS Agent system. All implementations must provide these interfaces
to ensure consistent and secure handling of sensitive information.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime

from ciris_engine.schemas.secrets_schemas_v1 import (
    SecretRecord,
    SecretPattern, 
    SecretsFilter,
    SecretReference,
    SecretAccessLog,
    DetectedSecret,
    SecretsFilterResult,
    RecallSecretParams,
    UpdateSecretsFilterParams
)


class SecretsFilterInterface(ABC):
    """Interface for detecting and filtering secrets from content"""
    
    @abstractmethod
    async def filter_content(self, content: str, source_id: str = None) -> SecretsFilterResult:
        """
        Scan content for secrets and replace them with UUID references
        
        Args:
            content: The text content to scan for secrets
            source_id: Optional identifier for the source of this content
            
        Returns:
            SecretsFilterResult with filtered content and detected secrets
        """
        pass
    
    @abstractmethod
    async def add_pattern(self, pattern: SecretPattern) -> bool:
        """
        Add a new secret detection pattern
        
        Args:
            pattern: The pattern definition to add
            
        Returns:
            True if pattern was added successfully
        """
        pass
    
    @abstractmethod
    async def remove_pattern(self, pattern_name: str) -> bool:
        """
        Remove a secret detection pattern
        
        Args:
            pattern_name: Name of the pattern to remove
            
        Returns:
            True if pattern was removed successfully
        """
        pass
    
    @abstractmethod
    async def get_filter_config(self) -> SecretsFilter:
        """
        Get the current filter configuration
        
        Returns:
            Current SecretsFilter configuration
        """
        pass
    
    @abstractmethod
    async def update_filter_config(self, updates: Dict[str, Any]) -> bool:
        """
        Update filter configuration settings
        
        Args:
            updates: Dictionary of configuration updates
            
        Returns:
            True if configuration was updated successfully
        """
        pass


class SecretsStoreInterface(ABC):
    """Interface for encrypted storage and retrieval of secrets"""
    
    @abstractmethod
    async def store_secret(self, secret: DetectedSecret, source_id: str = None) -> SecretRecord:
        """
        Store a detected secret securely
        
        Args:
            secret: The detected secret to store
            source_id: Optional identifier for the source
            
        Returns:
            SecretRecord with storage metadata
        """
        pass
    
    @abstractmethod
    async def retrieve_secret(self, secret_uuid: str, decrypt: bool = False) -> Optional[SecretRecord]:
        """
        Retrieve a stored secret by UUID
        
        Args:
            secret_uuid: UUID of the secret to retrieve
            decrypt: Whether to decrypt the secret value
            
        Returns:
            SecretRecord if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def delete_secret(self, secret_uuid: str) -> bool:
        """
        Permanently delete a stored secret
        
        Args:
            secret_uuid: UUID of the secret to delete
            
        Returns:
            True if secret was deleted successfully
        """
        pass
    
    @abstractmethod
    async def list_secrets(self, sensitivity_filter: str = None) -> List[SecretReference]:
        """
        List all stored secrets (metadata only)
        
        Args:
            sensitivity_filter: Optional filter by sensitivity level
            
        Returns:
            List of SecretReference objects
        """
        pass
    
    @abstractmethod
    async def update_access_log(self, log_entry: SecretAccessLog) -> None:
        """
        Record access to a secret in the audit log
        
        Args:
            log_entry: The access log entry to record
        """
        pass
    
    @abstractmethod
    async def get_access_logs(self, secret_uuid: str = None, limit: int = 100) -> List[SecretAccessLog]:
        """
        Retrieve access logs for auditing
        
        Args:
            secret_uuid: Optional filter by secret UUID
            limit: Maximum number of logs to return
            
        Returns:
            List of SecretAccessLog entries
        """
        pass
    
    @abstractmethod
    async def reencrypt_all(self, new_encryption_key: bytes) -> bool:
        """
        Re-encrypt all stored secrets with a new key (for key rotation)
        
        Args:
            new_encryption_key: The new encryption key to use
            
        Returns:
            True if re-encryption was successful
        """
        pass


class SecretsServiceInterface(ABC):
    """Main interface for coordinating secrets management"""
    
    @abstractmethod
    async def process_content(self, content: str, source_id: str = None) -> SecretsFilterResult:
        """
        Process content through the complete secrets pipeline
        
        Args:
            content: Content to process for secrets
            source_id: Optional source identifier
            
        Returns:
            SecretsFilterResult with filtered content and secrets stored
        """
        pass
    
    @abstractmethod
    async def decapsulate_secrets(self, content: Any, action_type: str = None) -> Any:
        """
        Replace secret UUIDs with actual values for action execution
        
        Args:
            content: Content that may contain secret UUID references
            action_type: Type of action being performed (for access control)
            
        Returns:
            Content with secrets decapsulated
        """
        pass
    
    @abstractmethod
    async def get_secret_references(self) -> List[SecretReference]:
        """
        Get references to all secrets for SystemSnapshot
        
        Returns:
            List of SecretReference objects for agent introspection
        """
        pass
    
    @abstractmethod
    async def recall_secret(self, params: RecallSecretParams, accessor: str) -> Dict[str, Any]:
        """
        Handle RECALL_SECRET tool requests
        
        Args:
            params: Parameters for the recall request
            accessor: Who/what is requesting the secret
            
        Returns:
            Dictionary with secret information (encrypted or decrypted)
        """
        pass
    
    @abstractmethod
    async def update_secrets_filter(self, params: UpdateSecretsFilterParams, accessor: str) -> Dict[str, Any]:
        """
        Handle UPDATE_SECRETS_FILTER tool requests
        
        Args:
            params: Parameters for the filter update
            accessor: Who/what is making the update
            
        Returns:
            Dictionary with operation result
        """
        pass
    
    @abstractmethod
    async def rotate_encryption_keys(self) -> bool:
        """
        Rotate encryption keys for all stored secrets
        
        Returns:
            True if key rotation was successful
        """
        pass


class SecretsEncryptionInterface(ABC):
    """Interface for cryptographic operations on secrets"""
    
    @abstractmethod
    def encrypt_secret(self, value: str) -> Tuple[bytes, bytes, bytes]:
        """
        Encrypt a secret value
        
        Args:
            value: The secret string to encrypt
            
        Returns:
            Tuple of (encrypted_value, salt, nonce)
        """
        pass
    
    @abstractmethod
    def decrypt_secret(self, encrypted_value: bytes, salt: bytes, nonce: bytes) -> str:
        """
        Decrypt a secret value
        
        Args:
            encrypted_value: The encrypted secret data
            salt: The salt used for key derivation
            nonce: The nonce used for encryption
            
        Returns:
            The decrypted secret string
        """
        pass
    
    @abstractmethod
    def rotate_master_key(self, new_master_key: bytes = None) -> bytes:
        """
        Rotate the master encryption key
        
        Args:
            new_master_key: New master key, or None to generate one
            
        Returns:
            The new master key that was set
        """
        pass
    
    @abstractmethod
    def test_encryption(self) -> bool:
        """
        Test that encryption/decryption is working correctly
        
        Returns:
            True if test passes, False otherwise
        """
        pass