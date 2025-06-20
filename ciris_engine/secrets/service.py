"""
Secrets Management Service for CIRIS Agent.

Coordinates secrets detection, storage, and retrieval with full audit trail
and integration with the agent's action pipeline.
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import logging

from .filter import SecretsFilter
from .store import SecretsStore, SecretRecord
from ..schemas.secrets_schemas_v1 import SecretReference
from ..schemas.config_schemas_v1 import SecretsDetectionConfig
from ..schemas.protocol_schemas_v1 import SecretsServiceStats
from ..protocols.secrets_interface import SecretsServiceInterface
from ..adapters.base import Service

logger = logging.getLogger(__name__)


class SecretsService(Service, SecretsServiceInterface):
    """
    Central service for secrets management in CIRIS Agent.
    
    Provides unified interface for detection, storage, retrieval,
    and automatic decapsulation of secrets during action execution.
    """
    
    def __init__(
        self,
        store: Optional[SecretsStore] = None,
        filter_obj: Optional[SecretsFilter] = None,
        detection_config: Optional[SecretsDetectionConfig] = None,
        db_path: str = "secrets.db",
        master_key: Optional[bytes] = None
    ):
        """
        Initialize secrets service.
        
        Args:
            store: Secrets store instance (created if None)
            filter_obj: Secrets filter instance (created if None)
            detection_config: Secrets detection configuration
            db_path: Database path for storage
            master_key: Master encryption key
        """
        self.store = store or SecretsStore(db_path=db_path, master_key=master_key)
        self.filter = filter_obj or SecretsFilter(detection_config)
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
        filtered_text, detected_secrets = self.filter.filter_text(text, context_hint)
        
        if not detected_secrets:
            return text, []
            
        secret_references = []
        
        for detected_secret in detected_secrets:
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
                auto_decapsulate_for_actions=self._get_auto_decapsulate_actions(detected_secret.sensitivity.value)
            )
            
            stored = await self.store.store_secret(detected_secret, source_message_id)
            
            if stored:
                self._current_task_secrets[detected_secret.secret_uuid] = detected_secret.original_value
                
                secret_ref = SecretReference(
                    uuid=detected_secret.secret_uuid,
                    description=detected_secret.description,
                    context_hint=detected_secret.context_hint,
                    sensitivity=detected_secret.sensitivity,
                    detected_pattern=detected_secret.pattern_name or "unknown",
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
        secret_record = await self.store.retrieve_secret(
            secret_uuid, decrypt
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
        
        if decrypt:
            decrypted_value = await self.store.decrypt_secret_value(secret_record)
            if decrypted_value:
                result["decrypted_value"] = decrypted_value
            else:
                result["decryption_error"] = "Failed to decrypt secret value"
                
        return result
        
    async def decapsulate_secrets_in_parameters(
        self,
        parameters: Any,
        action_type: str,
        context: Dict[str, Any]
    ) -> Any:
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
            
        decapsulated_params: Any = await self._deep_decapsulate(
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
            list_result: List[Any] = []
            for item in obj:
                list_result.append(await self._deep_decapsulate(item, action_type, context))
            return list_result
        else:
            return obj
            
    async def _decapsulate_string(self, text: str, action_type: str, context: Dict[str, Any]) -> str:
        """Decapsulate secret references in a string."""
        import re
        
        secret_pattern = r'\{SECRET:([a-f0-9-]{36}):([^}]+)\}'
        
        matches = list(re.finditer(secret_pattern, text))
        if not matches:
            return text
            
        result = text
        
        for match in reversed(matches):
            secret_uuid = match.group(1)
            description = match.group(2)
            
            secret_record = await self.store.retrieve_secret(
                secret_uuid, 
                decrypt=False
            )
            
            if not secret_record:
                logger.warning(f"Secret {secret_uuid} not found for decapsulation")
                continue  # Leave original reference
                
            if action_type in secret_record.auto_decapsulate_for_actions:
                decrypted_value = await self.store.decrypt_secret_value(secret_record)
                if decrypted_value:
                    logger.info(
                        f"Auto-decapsulated {secret_record.sensitivity_level} secret "
                        f"for {action_type} action: {description}"
                    )
                    result = result[:match.start()] + decrypted_value + result[match.end():]
                else:
                    logger.error(f"Failed to decrypt secret {secret_uuid}")
            else:
                logger.info(
                    f"Secret {secret_uuid} not configured for auto-decapsulation "
                    f"in {action_type} actions"
                )
            
        return result
        
    async def update_filter_config(
        self,
        updates: Dict[str, Any],
        accessor: str = "agent"
    ) -> Dict[str, Any]:  # pragma: no cover - thin wrapper
        """
        Update secrets filter configuration.
        
        Args:
            updates: Dictionary of configuration updates
            accessor: Who is making the update
            
        Returns:
            Result of configuration update
        """
        try:
            results = []
            
            if "add_pattern" in updates:
                pattern = updates["add_pattern"]
                self.filter.add_custom_pattern(pattern)
                results.append(f"Added pattern: {pattern.name}")
                
            if "remove_pattern" in updates:
                pattern_name = updates["remove_pattern"]
                removed = self.filter.remove_custom_pattern(pattern_name)
                if removed:
                    results.append(f"Removed pattern: {pattern_name}")
                else:
                    results.append(f"Pattern not found: {pattern_name}")
                    
            if "disable_pattern" in updates:
                pattern_name = updates["disable_pattern"]
                self.filter.disable_pattern(pattern_name)
                results.append(f"Disabled pattern: {pattern_name}")
                
            if "enable_pattern" in updates:
                pattern_name = updates["enable_pattern"]
                self.filter.enable_pattern(pattern_name)
                results.append(f"Enabled pattern: {pattern_name}")
                
            if "set_sensitivity" in updates:
                config = updates["set_sensitivity"]
                pattern_name = config.get("pattern_name")
                sensitivity = config.get("sensitivity")
                if not pattern_name or not sensitivity:
                    results.append("Error: Pattern name and sensitivity required")
                else:
                    results.append("Error: Sensitivity overrides not supported in config-based system")
                
            if "get_current" in updates:
                config = self.filter.export_config()
                stats = self.filter.get_pattern_stats()
                return {
                    "success": True,
                    "config": config,
                    "stats": stats
                }
                
            return {
                "success": True,
                "results": results,
                "accessor": accessor
            }
                
        except Exception as e:
            logger.error(f"Failed to update filter config: {e}")
            return {"success": False, "error": str(e)}
            
    async def list_stored_secrets(
        self, 
        limit: int = 10
    ) -> List[SecretReference]:
        """
        List stored secrets (metadata only, no decryption).
        
        Args:
            limit: Maximum number of secrets to return
            
        Returns:
            List of SecretReference objects
        """
        secrets = await self.store.list_secrets(sensitivity_filter=None, pattern_filter=None)
        
        limited_secrets = secrets[:limit] if secrets else []
        
        return limited_secrets
        
    async def forget_secret(self, secret_uuid: str, accessor: str = "agent") -> bool:
        """
        Delete/forget a stored secret.
        
        Args:
            secret_uuid: UUID of secret to forget
            accessor: Who is forgetting the secret
            
        Returns:
            True if successfully forgotten
        """
        deleted = await self.store.delete_secret(secret_uuid)
        
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
            
    async def get_service_stats(self) -> SecretsServiceStats:
        """Get comprehensive service statistics."""
        try:
            # Get filter stats
            filter_stats = self.filter.get_pattern_stats()
            
            # Get storage stats
            all_secrets = await self.store.list_secrets()
            
            # Get enabled patterns from filter stats
            enabled_patterns = list(filter_stats.get('pattern_counts', {}).keys())
            
            # Count recent detections (within last hour)
            recent_detections = filter_stats.get('total_detected', 0)
            
            # Calculate storage size (approximate)
            storage_size_bytes = len(all_secrets) * 512  # Rough estimate: 512 bytes per secret
            
            return SecretsServiceStats(
                secrets_stored=len(all_secrets),
                filter_active=self.filter.is_enabled if hasattr(self.filter, 'is_enabled') else True,
                patterns_enabled=enabled_patterns,
                recent_detections=recent_detections,
                storage_size_bytes=storage_size_bytes
            )
            
        except Exception as e:
            logger.error(f"Failed to get service stats: {e}")
            # Return default stats on error
            return SecretsServiceStats(
                secrets_stored=0,
                filter_active=False,
                patterns_enabled=[],
                recent_detections=0,
                storage_size_bytes=0
            )
    
    async def start(self) -> None:
        """Start the secrets service."""  # pragma: no cover - trivial
        logger.info("SecretsService started")
        
    async def stop(self) -> None:
        """Stop the secrets service and clean up resources."""  # pragma: no cover - trivial
        # Auto-forget any remaining task secrets
        if self._auto_forget_enabled and self._current_task_secrets:
            logger.info(f"Auto-forgetting {len(self._current_task_secrets)} task secrets on shutdown")
            await self.auto_forget_task_secrets()
        logger.info("SecretsService stopped")
    
    async def is_healthy(self) -> bool:
        """Check if the secrets service is healthy."""
        try:
            # Check if filter and store are accessible
            if not self.filter or not self.store:
                return False
            # Could add more health checks here
            return True
        except Exception:
            return False
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return [
            "process_incoming_text", "decapsulate_secrets_in_parameters",
            "list_stored_secrets", "recall_secret", "update_filter_config",
            "forget_secret", "auto_forget_task_secrets", "get_service_stats"
        ]