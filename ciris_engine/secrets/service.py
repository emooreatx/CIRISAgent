"""
Secrets Management Service for CIRIS Agent.

Coordinates secrets detection, storage, and retrieval with full audit trail
and integration with the agent's action pipeline.
"""
import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import logging

from .filter import SecretsFilter, DetectedSecret, SecretsFilterConfig
from .store import SecretsStore, SecretRecord
from ..schemas.context_schemas_v1 import SecretReference
from ..protocols.secrets_interface import SecretsServiceInterface

logger = logging.getLogger(__name__)


class SecretsService(SecretsServiceInterface):
    """
    Central service for secrets management in CIRIS Agent.
    
    Provides unified interface for detection, storage, retrieval,
    and automatic decapsulation of secrets during action execution.
    """
    
    def __init__(
        self,
        store: Optional[SecretsStore] = None,
        filter_obj: Optional[SecretsFilter] = None,
        db_path: str = "secrets.db",
        master_key: Optional[bytes] = None
    ):
        """
        Initialize secrets service.
        
        Args:
            store: Secrets store instance (created if None)
            filter_obj: Secrets filter instance (created if None)
            db_path: Database path for storage
            master_key: Master encryption key
        """
        self.store = store or SecretsStore(db_path=db_path, master_key=master_key)
        self.filter = filter_obj or SecretsFilter()
        self._auto_forget_enabled = True
        self._current_task_secrets: Dict[str, str] = {}  # UUID -> original_value
        
    async def process_incoming_text(
        self, 
        text: str, 
        context_hint: str = "",
        source_message_id: Optional[str] = None
    ) -> Tuple[str, List[SecretReference]]:
        """
        Process incoming text for secrets detection and replacement.
        
        Args:
            text: Original text to process
            context_hint: Safe context description
            source_message_id: ID of source message for tracking
            
        Returns:
            Tuple of (filtered_text, secret_references)
        """
        # Detect secrets in text
        filtered_text, detected_secrets = self.filter.filter_text(text, context_hint)
        
        if not detected_secrets:
            return text, []
            
        # Store detected secrets and create references
        secret_references = []
        
        for detected_secret in detected_secrets:
            # Create secret record
            secret_record = SecretRecord(
                secret_uuid=detected_secret.secret_uuid,
                encrypted_value=b"",  # Will be set by store
                encryption_key_ref="",  # Will be set by store
                salt=b"",  # Will be set by store
                nonce=b"",  # Will be set by store
                description=detected_secret.description,
                sensitivity_level=detected_secret.sensitivity,
                detected_pattern=detected_secret.pattern_name,
                context_hint=detected_secret.context_hint,
                created_at=datetime.now(),
                source_message_id=source_message_id,
                auto_decapsulate_for_actions=self._get_auto_decapsulate_actions(detected_secret.sensitivity)
            )
            
            # Store encrypted secret
            stored = await self.store.store_secret(secret_record, detected_secret.original_text)
            
            if stored:
                # Track for potential auto-forget
                self._current_task_secrets[detected_secret.secret_uuid] = detected_secret.original_text
                
                # Create reference for context
                secret_ref = SecretReference(
                    uuid=detected_secret.secret_uuid,
                    description=detected_secret.description,
                    context_hint=detected_secret.context_hint,
                    sensitivity=detected_secret.sensitivity,
                    auto_decapsulate_actions=secret_record.auto_decapsulate_for_actions,
                    created_at=secret_record.created_at,
                    last_accessed=None
                )
                secret_references.append(secret_ref)
                
                logger.info(
                    f"Detected and stored {detected_secret.sensitivity} secret: "
                    f"{detected_secret.description} (UUID: {detected_secret.secret_uuid})"
                )
                
        return filtered_text, secret_references
        
    async def recall_secret(
        self, 
        secret_uuid: str, 
        purpose: str,
        accessor: str = "agent",
        decrypt: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Recall a stored secret for agent use.
        
        Args:
            secret_uuid: UUID of secret to recall
            purpose: Purpose for accessing secret (for audit)
            accessor: Who is accessing the secret
            decrypt: Whether to return decrypted value
            
        Returns:
            Secret information dict or None if not found/denied
        """
        # Retrieve secret record
        secret_record = await self.store.retrieve_secret(
            secret_uuid, purpose, accessor, decrypt
        )
        
        if not secret_record:
            return None
            
        result = {
            "uuid": secret_record.secret_uuid,
            "description": secret_record.description,
            "sensitivity": secret_record.sensitivity_level,
            "pattern": secret_record.detected_pattern,
            "context_hint": secret_record.context_hint,
            "created_at": secret_record.created_at.isoformat(),
            "last_accessed": secret_record.last_accessed.isoformat() if secret_record.last_accessed else None,
            "access_count": secret_record.access_count,
            "auto_decapsulate_actions": secret_record.auto_decapsulate_for_actions
        }
        
        # Include decrypted value if requested and authorized
        if decrypt:
            decrypted_value = await self.store.decrypt_secret_value(secret_record)
            if decrypted_value:
                result["decrypted_value"] = decrypted_value
            else:
                result["decryption_error"] = "Failed to decrypt secret value"
                
        return result
        
    async def decapsulate_secrets_in_parameters(
        self,
        parameters: Dict[str, Any],
        action_type: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Automatically decapsulate secrets in action parameters.
        
        Args:
            parameters: Action parameters potentially containing secret references
            action_type: Type of action being executed
            context: Execution context for audit
            
        Returns:
            Parameters with secrets decapsulated where appropriate
        """
        if not parameters:
            return parameters
            
        # Deep copy to avoid modifying original
        decapsulated_params = await self._deep_decapsulate(
            parameters, action_type, context
        )
        
        return decapsulated_params
        
    async def _deep_decapsulate(
        self, 
        obj: Any, 
        action_type: str, 
        context: Dict[str, Any]
    ) -> Any:
        """Recursively decapsulate secrets in nested structures."""
        if isinstance(obj, str):
            return await self._decapsulate_string(obj, action_type, context)
        elif isinstance(obj, dict):
            result: Dict[str, Any] = {}
            for key, value in obj.items():
                result[key] = await self._deep_decapsulate(value, action_type, context)
            return result
        elif isinstance(obj, list):
            result: List[Any] = []
            for item in obj:
                result.append(await self._deep_decapsulate(item, action_type, context))
            return result
        else:
            return obj
            
    async def _decapsulate_string(self, text: str, action_type: str, context: Dict[str, Any]) -> str:
        """Decapsulate secret references in a string."""
        import re
        
        # Pattern to match secret references: {SECRET:uuid:description}
        secret_pattern = r'\{SECRET:([a-f0-9-]{36}):([^}]+)\}'
        
        # Find all matches
        matches = list(re.finditer(secret_pattern, text))
        if not matches:
            return text
            
        result = text
        
        # Process matches in reverse order to maintain positions
        for match in reversed(matches):
            secret_uuid = match.group(1)
            description = match.group(2)
            
            # Check if this action type is allowed auto-decapsulation
            secret_record = await self.store.retrieve_secret(
                secret_uuid, 
                f"Auto-decapsulation for {action_type}",
                "system",
                decrypt=False
            )
            
            if not secret_record:
                logger.warning(f"Secret {secret_uuid} not found for decapsulation")
                continue  # Leave original reference
                
            if action_type in secret_record.auto_decapsulate_for_actions:
                # Decrypt and return actual value
                decrypted_value = await self.store.decrypt_secret_value(secret_record)
                if decrypted_value:
                    logger.info(
                        f"Auto-decapsulated {secret_record.sensitivity_level} secret "
                        f"for {action_type} action: {description}"
                    )
                    # Replace the secret reference with the actual value
                    result = result[:match.start()] + decrypted_value + result[match.end():]
                else:
                    logger.error(f"Failed to decrypt secret {secret_uuid}")
                    # Leave original reference
            else:
                logger.info(
                    f"Secret {secret_uuid} not configured for auto-decapsulation "
                    f"in {action_type} actions"
                )
                # Leave original reference
            
        return result
        
    async def update_filter_config(
        self,
        operation: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Update secrets filter configuration.
        
        Args:
            operation: Operation type (add_pattern, remove_pattern, etc.)
            **kwargs: Operation-specific parameters
            
        Returns:
            Result of configuration update
        """
        try:
            if operation == "add_pattern":
                pattern = kwargs.get("pattern")
                if not pattern:
                    return {"success": False, "error": "Pattern required"}
                    
                self.filter.add_custom_pattern(pattern)
                return {"success": True, "message": f"Added pattern: {pattern.name}"}
                
            elif operation == "remove_pattern":
                pattern_name = kwargs.get("pattern_name")
                if not pattern_name:
                    return {"success": False, "error": "Pattern name required"}
                    
                removed = self.filter.remove_custom_pattern(pattern_name)
                if removed:
                    return {"success": True, "message": f"Removed pattern: {pattern_name}"}
                else:
                    return {"success": False, "error": f"Pattern not found: {pattern_name}"}
                    
            elif operation == "disable_pattern":
                pattern_name = kwargs.get("pattern_name")
                if not pattern_name:
                    return {"success": False, "error": "Pattern name required"}
                    
                self.filter.disable_pattern(pattern_name)
                return {"success": True, "message": f"Disabled pattern: {pattern_name}"}
                
            elif operation == "enable_pattern":
                pattern_name = kwargs.get("pattern_name")
                if not pattern_name:
                    return {"success": False, "error": "Pattern name required"}
                    
                self.filter.enable_pattern(pattern_name)
                return {"success": True, "message": f"Enabled pattern: {pattern_name}"}
                
            elif operation == "set_sensitivity":
                pattern_name = kwargs.get("pattern_name")
                sensitivity = kwargs.get("sensitivity")
                if not pattern_name or not sensitivity:
                    return {"success": False, "error": "Pattern name and sensitivity required"}
                    
                self.filter.set_sensitivity_override(pattern_name, sensitivity)
                return {"success": True, "message": f"Set {pattern_name} sensitivity to {sensitivity}"}
                
            elif operation == "get_current":
                config = self.filter.export_config()
                stats = self.filter.get_pattern_stats()
                return {
                    "success": True,
                    "config": config,
                    "stats": stats
                }
                
            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}
                
        except Exception as e:
            logger.error(f"Failed to update filter config: {e}")
            return {"success": False, "error": str(e)}
            
    async def list_stored_secrets(
        self,
        pattern_filter: Optional[str] = None,
        sensitivity_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List stored secrets (metadata only, no decryption).
        
        Args:
            pattern_filter: Filter by detection pattern
            sensitivity_filter: Filter by sensitivity level
            
        Returns:
            List of secret metadata
        """
        secrets = await self.store.list_secrets(pattern_filter, sensitivity_filter)
        
        result = []
        for secret in secrets:
            result.append({
                "uuid": secret.uuid,
                "description": secret.description,
                "sensitivity": secret.sensitivity,
                "context_hint": secret.context_hint,
                "created_at": secret.created_at.isoformat(),
                "last_accessed": secret.last_accessed.isoformat() if secret.last_accessed else None,
                "auto_decapsulate_actions": secret.auto_decapsulate_actions
            })
            
        return result
        
    async def forget_secret(self, secret_uuid: str, accessor: str = "agent") -> bool:
        """
        Delete/forget a stored secret.
        
        Args:
            secret_uuid: UUID of secret to forget
            accessor: Who is forgetting the secret
            
        Returns:
            True if successfully forgotten
        """
        deleted = await self.store.delete_secret(secret_uuid, accessor)
        
        # Remove from current task tracking
        if secret_uuid in self._current_task_secrets:
            del self._current_task_secrets[secret_uuid]
            
        return deleted
        
    async def auto_forget_task_secrets(self) -> List[str]:
        """
        Automatically forget secrets from current task.
        
        Returns:
            List of forgotten secret UUIDs
        """
        if not self._auto_forget_enabled:
            return []
            
        forgotten_secrets = []
        
        for secret_uuid in list(self._current_task_secrets.keys()):
            deleted = await self.forget_secret(secret_uuid, "auto_forget")
            if deleted:
                forgotten_secrets.append(secret_uuid)
                
        self._current_task_secrets.clear()
        
        if forgotten_secrets:
            logger.info(f"Auto-forgot {len(forgotten_secrets)} task secrets")
            
        return forgotten_secrets
        
    def enable_auto_forget(self) -> None:
        """Enable automatic forgetting of task secrets."""
        self._auto_forget_enabled = True
        
    def disable_auto_forget(self) -> None:
        """Disable automatic forgetting of task secrets."""
        self._auto_forget_enabled = False
        
    def _get_auto_decapsulate_actions(self, sensitivity: str) -> List[str]:
        """
        Get default auto-decapsulation actions based on sensitivity.
        
        Args:
            sensitivity: Secret sensitivity level
            
        Returns:
            List of action types that can auto-decapsulate this secret
        """
        if sensitivity == "CRITICAL":
            return []  # Require manual access for critical secrets
        elif sensitivity == "HIGH":
            return ["tool"]  # Only tool actions for high sensitivity
        elif sensitivity == "MEDIUM":
            return ["tool", "speak"]  # Tool and speak actions
        else:  # LOW
            return ["tool", "speak", "memorize"]  # Most actions allowed
            
    async def get_service_stats(self) -> Dict[str, Any]:
        """Get comprehensive service statistics."""
        try:
            # Get filter stats
            filter_stats = self.filter.get_pattern_stats()
            
            # Get storage stats
            all_secrets = await self.store.list_secrets()
            
            sensitivity_counts = {}
            pattern_counts = {}
            
            for secret in all_secrets:
                # Count by sensitivity
                sensitivity_counts[secret.sensitivity] = (
                    sensitivity_counts.get(secret.sensitivity, 0) + 1
                )
                
                # Note: SecretReference doesn't have detected_pattern, skip pattern counting
                
            return {
                "filter_stats": filter_stats,
                "storage_stats": {
                    "total_secrets": len(all_secrets),
                    "sensitivity_distribution": sensitivity_counts,
                    "pattern_distribution": pattern_counts,
                    "current_task_secrets": len(self._current_task_secrets),
                    "auto_forget_enabled": self._auto_forget_enabled
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get service stats: {e}")
            return {"error": str(e)}
    
    async def start(self) -> None:
        """Start the secrets service."""
        logger.info("SecretsService started")
        
    async def stop(self) -> None:
        """Stop the secrets service and clean up resources."""
        # Auto-forget any remaining task secrets
        if self._auto_forget_enabled and self._current_task_secrets:
            logger.info(f"Auto-forgetting {len(self._current_task_secrets)} task secrets on shutdown")
            await self.auto_forget_task_secrets()
        logger.info("SecretsService stopped")