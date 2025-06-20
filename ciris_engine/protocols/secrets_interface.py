"""
Secrets Management Interface Protocols

Defines the contracts for secure secrets detection, storage, and access control
within the CIRIS Agent system. All implementations must provide these interfaces
to ensure consistent and secure handling of sensitive information.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any, Tuple

from ciris_engine.schemas.secrets_schemas_v1 import (
    SecretRecord,
    SecretReference,
    SecretAccessLog,
    DetectedSecret,
    SecretsFilterResult
)
from ciris_engine.schemas.config_schemas_v1 import (
    SecretsFilter,
    SecretPattern
)
from ciris_engine.schemas.protocol_schemas_v1 import SecretsServiceStats


class SecretsFilterInterface(ABC):
    """Interface for detecting and filtering secrets from content"""
    
    @abstractmethod
    async def filter_content(self, content: str, source_id: Optional[str] = None) -> SecretsFilterResult:
        """
        Scan content for secrets and replace them with UUID references
        
        Args:
            content: The text content to scan for secrets
            source_id: Optional identifier for the source of this content
            
        Returns:
            SecretsFilterResult with filtered content and detected secrets
        """
    
    @abstractmethod
    async def add_pattern(self, pattern: SecretPattern) -> bool:
        """
        Add a new secret detection pattern
        
        Args:
            pattern: The pattern definition to add
            
        Returns:
            True if pattern was added successfully
        """
    
    @abstractmethod
    async def remove_pattern(self, pattern_name: str) -> bool:
        """
        Remove a secret detection pattern
        
        Args:
            pattern_name: Name of the pattern to remove
            
        Returns:
            True if pattern was removed successfully
        """
    
    @abstractmethod
    async def get_filter_config(self) -> SecretsFilter:
        """
        Get the current filter configuration
        
        Returns:
            Current SecretsFilter configuration
        """
    
    @abstractmethod
    async def update_filter_config(self, updates: Dict[str, Any]) -> bool:
        """
        Update filter configuration settings
        
        Args:
            updates: Dictionary of configuration updates
            
        Returns:
            True if configuration was updated successfully
        """


class SecretsStoreInterface(ABC):
    """Interface for encrypted storage and retrieval of secrets"""
    
    @abstractmethod
    async def store_secret(self, secret: DetectedSecret, source_id: Optional[str] = None) -> SecretRecord:
        """
        Store a detected secret securely
        
        Args:
            secret: The detected secret to store
            source_id: Optional identifier for the source
            
        Returns:
            SecretRecord with storage metadata
        """
    
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
    
    @abstractmethod
    async def delete_secret(self, secret_uuid: str) -> bool:
        """
        Permanently delete a stored secret
        
        Args:
            secret_uuid: UUID of the secret to delete
            
        Returns:
            True if secret was deleted successfully
        """
    
    @abstractmethod
    async def list_secrets(self, sensitivity_filter: Optional[str] = None, pattern_filter: Optional[str] = None) -> List[SecretReference]:
        """
        List all stored secrets (metadata only)
        
        Args:
            sensitivity_filter: Optional filter by sensitivity level
            pattern_filter: Optional filter by detected pattern name
            
        Returns:
            List of SecretReference objects
        """
    
    @abstractmethod
    async def update_access_log(self, log_entry: SecretAccessLog) -> None:
        """
        Record access to a secret in the audit log
        
        Args:
            log_entry: The access log entry to record
        """
    
    @abstractmethod
    async def get_access_logs(self, secret_uuid: Optional[str] = None, limit: int = 100) -> List[SecretAccessLog]:
        """
        Retrieve access logs for auditing
        
        Args:
            secret_uuid: Optional filter by secret UUID
            limit: Maximum number of logs to return
            
        Returns:
            List of SecretAccessLog entries
        """
    
    @abstractmethod
    async def reencrypt_all(self, new_encryption_key: bytes) -> bool:
        """
        Re-encrypt all stored secrets with a new key (for key rotation)
        
        Args:
            new_encryption_key: The new encryption key to use
            
        Returns:
            True if re-encryption was successful
        """


class SecretsServiceInterface(ABC):
    """Main interface for coordinating secrets management"""
    
    @abstractmethod
    async def process_incoming_text(self, text: str, context_hint: str = "", source_message_id: Optional[str] = None) -> Tuple[str, List['SecretReference']]:
        """
        Process incoming text for secrets detection and replacement
        
        Args:
            text: Original text to process
            context_hint: Safe context description
            source_message_id: ID of source message for tracking
            
        Returns:
            Tuple of (filtered_text, secret_references)
        """
    
    @abstractmethod
    async def decapsulate_secrets_in_parameters(self, parameters: Any, action_type: str, context: Dict[str, Any]) -> Any:
        """
        Replace secret UUIDs with actual values in action parameters
        
        Args:
            parameters: Action parameters that may contain secret UUID references
            action_type: Type of action being performed (for access control)
            context: Context information for the decapsulation
            
        Returns:
            Parameters with secrets decapsulated
        """
    
    @abstractmethod
    async def list_stored_secrets(self, limit: int = 10) -> List['SecretReference']:
        """
        Get references to stored secrets for SystemSnapshot
        
        Args:
            limit: Maximum number of secrets to return
            
        Returns:
            List of SecretReference objects for agent introspection
        """
    
    @abstractmethod
    async def recall_secret(self, secret_uuid: str, purpose: str, accessor: str = "agent", decrypt: bool = False) -> Optional[Dict[str, Any]]:
        """
        Recall a stored secret for agent use
        
        Args:
            secret_uuid: UUID of secret to recall
            purpose: Purpose for accessing secret (for audit)
            accessor: Who is accessing the secret
            decrypt: Whether to return decrypted value
            
        Returns:
            Secret information dict or None if not found/denied
        """
    
    @abstractmethod
    async def update_filter_config(self, updates: Dict[str, Any], accessor: str = "agent") -> Dict[str, Any]:
        """
        Update filter configuration settings
        
        Args:
            updates: Dictionary of configuration updates
            accessor: Who is making the update
            
        Returns:
            Dictionary with operation result
        """
    
    @abstractmethod
    async def forget_secret(self, secret_uuid: str, accessor: str = "agent") -> bool:
        """
        Delete/forget a stored secret
        
        Args:
            secret_uuid: UUID of secret to forget
            accessor: Who is forgetting the secret
            
        Returns:
            True if successfully forgotten
        """
    
    # Non-abstract methods can be implemented optionally
    async def get_service_stats(self) -> SecretsServiceStats:
        """
        Get service statistics for monitoring
        
        Returns:
            SecretsServiceStats with service statistics
        """
        from ciris_engine.schemas.protocol_schemas_v1 import SecretsServiceStats
        return SecretsServiceStats(
            secrets_stored=0, 
            filter_active=True, 
            patterns_enabled=[],
            recent_detections=0,
            storage_size_bytes=None
        )
    
    async def auto_forget_task_secrets(self) -> List[str]:
        """
        Automatically forget secrets from current task
        
        Returns:
            List of forgotten secret UUIDs
        """
        return []


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
    
    @abstractmethod
    def rotate_master_key(self, new_master_key: Optional[bytes] = None) -> bytes:
        """
        Rotate the master encryption key
        
        Args:
            new_master_key: New master key, or None to generate one
            
        Returns:
            The new master key that was set
        """
    
    @abstractmethod
    def test_encryption(self) -> bool:
        """
        Test that encryption/decryption is working correctly
        
        Returns:
            True if test passes, False otherwise
        """
