"""
Secrets message bus - handles all secrets service operations with enhanced security
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from ciris_engine.schemas.foundational_schemas_v1 import ServiceType
from ciris_engine.schemas.secrets_schemas_v1 import SecretReference
from ciris_engine.schemas.protocol_schemas_v1 import SecretInfo
from typing import Tuple
from ciris_engine.protocols.services import SecretsService
from .base_bus import BaseBus, BusMessage

logger = logging.getLogger(__name__)


class SecretsBus(BaseBus[SecretsService]):
    """
    Message bus for all secrets operations.
    
    CRITICAL: This bus handles security-sensitive operations and includes:
    - Rate limiting per handler
    - Full audit trail of all operations
    - Access control validation
    - Secure queue handling
    """
    
    def __init__(self, service_registry: Any):
        super().__init__(
            service_type=ServiceType.SECRETS,
            service_registry=service_registry
        )
        # Track rate limits per handler
        self._handler_call_counts: Dict[str, Dict[str, List[float]]] = {}
        self._rate_limit_window = 60  # seconds
        self._max_calls_per_minute = {
            "process_incoming_text": 100,
            "recall_secret": 50,
            "forget_secret": 20,
            "update_filter_config": 10,
            "decapsulate_secrets": 30
        }
    
    async def process_incoming_text(
        self,
        text: str,
        context_hint: str = "",
        source_message_id: Optional[str] = None,
        handler_name: str = "default"
    ) -> Tuple[str, List[SecretReference]]:
        """Process incoming text for secrets detection and replacement with rate limiting"""
        if not self._check_rate_limit(handler_name, "process_incoming_text"):
            logger.warning(f"Rate limit exceeded for {handler_name} on process_incoming_text")
            return (text, [])
        
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["process_incoming_text"]
        )
        
        if not service:
            logger.error(f"No secrets service available for {handler_name}")
            return (text, [])
        
        try:
            # Log the operation for audit
            logger.info(f"Secrets processing requested by {handler_name}, context: {context_hint}")
            filtered_text, secret_refs = await service.process_incoming_text(text, context_hint, source_message_id)
            
            # Audit if secrets were found
            if secret_refs:
                logger.warning(
                    f"Secrets detected by {handler_name}: count={len(secret_refs)}"
                )
            
            return (filtered_text, secret_refs)
        except Exception as e:
            logger.error(f"Failed to process text for secrets: {e}", exc_info=True)
            return (text, [])
    
    async def recall_secret(
        self,
        secret_uuid: str,
        purpose: str,
        accessor: Optional[str] = None,
        decrypt: bool = False,
        handler_name: str = "default"
    ) -> Optional[SecretInfo]:
        """Recall a stored secret with audit logging"""
        if not self._check_rate_limit(handler_name, "recall_secret"):
            logger.warning(f"Rate limit exceeded for {handler_name} on recall_secret")
            return None
        
        # Use handler_name as accessor if not provided
        if accessor is None:
            accessor = handler_name
        
        logger.info(
            f"Secret recall requested by {handler_name}: uuid={secret_uuid}, purpose={purpose}, decrypt={decrypt}"
        )
        
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["recall_secret"]
        )
        
        if not service:
            logger.error(f"No secrets service available for {handler_name}")
            return None
        
        try:
            result = await service.recall_secret(secret_uuid, purpose, accessor, decrypt)
            
            if result:
                logger.info(
                    f"Secret recalled successfully by {handler_name}: uuid={secret_uuid}"
                )
            else:
                logger.warning(
                    f"Secret not found or access denied for {handler_name}: uuid={secret_uuid}"
                )
            
            return result
        except Exception as e:
            logger.error(f"Failed to recall secret: {e}", exc_info=True)
            return None
    
    async def forget_secret(
        self,
        secret_uuid: str,
        accessor: Optional[str] = None,
        handler_name: str = "default"
    ) -> bool:
        """Forget/delete a secret with audit trail"""
        # Use handler_name as accessor if not provided
        if accessor is None:
            accessor = handler_name
            
        logger.warning(
            f"Secret deletion requested by {handler_name}: uuid={secret_uuid}, accessor={accessor}"
        )
        
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["forget_secret"]
        )
        
        if not service:
            logger.error(f"No secrets service available for {handler_name}")
            return False
        
        try:
            success = await service.forget_secret(secret_uuid, accessor)
            
            if success:
                logger.warning(
                    f"Secret deleted by {handler_name}: uuid={secret_uuid}"
                )
            else:
                logger.error(
                    f"Failed to delete secret for {handler_name}: uuid={secret_uuid}"
                )
            
            return success
        except Exception as e:
            logger.error(f"Failed to delete secret: {e}", exc_info=True)
            return False
    
    async def decapsulate_secrets_in_parameters(
        self,
        parameters: Any,
        action_type: str,
        context: Dict[str, Any],
        handler_name: str = "default"
    ) -> Any:
        """Decapsulate secrets in parameters with full context logging"""
        if not self._check_rate_limit(handler_name, "decapsulate_secrets"):
            logger.warning(f"Rate limit exceeded for {handler_name} on decapsulate_secrets")
            return parameters
        
        logger.info(
            f"Secret decapsulation requested by {handler_name}: action={action_type}, context_keys={list(context.keys())}"
        )
        
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["decapsulate_secrets_in_parameters"]
        )
        
        if not service:
            logger.error(f"No secrets service available for {handler_name}")
            return parameters
        
        try:
            result = await service.decapsulate_secrets_in_parameters(
                parameters, action_type, context
            )
            
            # Log if any secrets were decapsulated
            if result != parameters:
                logger.info(
                    f"Secrets decapsulated for {handler_name}: action={action_type}"
                )
            
            return result
        except Exception as e:
            logger.error(f"Failed to decapsulate secrets: {e}", exc_info=True)
            return parameters
    
    async def update_filter_config(
        self,
        updates: Dict[str, Any],
        accessor: Optional[str] = None,
        handler_name: str = "default"
    ) -> Dict[str, Any]:
        """Update filter configuration with audit logging"""
        # Use handler_name as accessor if not provided
        if accessor is None:
            accessor = handler_name
            
        logger.info(
            f"Filter config update requested by {handler_name}: updates={list(updates.keys())}"
        )
        
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["update_filter_config"]
        )
        
        if not service:
            logger.error(f"No secrets service available for {handler_name}")
            return {"error": "Service unavailable"}
        
        try:
            result = await service.update_filter_config(updates, accessor)
            
            logger.info(
                f"Filter config updated by {handler_name}: result={result}"
            )
            
            return result
        except Exception as e:
            logger.error(f"Failed to update filter config: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def is_healthy(self, handler_name: str = "default") -> bool:
        """Check if secrets service is healthy"""
        service = await self.get_service(handler_name=handler_name)
        if not service:
            return False
        try:
            return await service.is_healthy()
        except Exception as e:
            logger.error(f"Failed to check health: {e}")
            return False
    
    async def get_capabilities(self, handler_name: str = "default") -> List[str]:
        """Get secrets service capabilities"""
        service = await self.get_service(handler_name=handler_name)
        if not service:
            return []
        try:
            return await service.get_capabilities()
        except Exception as e:
            logger.error(f"Failed to get capabilities: {e}")
            return []
    
    def _check_rate_limit(self, handler_name: str, operation: str) -> bool:
        """Check if handler has exceeded rate limit for operation"""
        now = datetime.now().timestamp()
        
        # Initialize handler tracking if needed
        if handler_name not in self._handler_call_counts:
            self._handler_call_counts[handler_name] = {}
        
        # Clean old entries
        cutoff = now - self._rate_limit_window
        if operation in self._handler_call_counts[handler_name]:
            self._handler_call_counts[handler_name][operation] = [
                ts for ts in self._handler_call_counts[handler_name][operation]
                if ts > cutoff
            ]
        
        # Count calls in current window
        calls_in_window = len(
            self._handler_call_counts[handler_name].get(operation, [])
        )
        
        # Check limit
        limit = self._max_calls_per_minute.get(operation, 50)
        if calls_in_window >= limit:
            return False
        
        # Record this call
        if operation not in self._handler_call_counts[handler_name]:
            self._handler_call_counts[handler_name][operation] = []
        self._handler_call_counts[handler_name][operation].append(now)
        
        return True
    
    async def _process_message(self, message: BusMessage) -> None:
        """Process a secrets message - currently all operations are synchronous"""
        logger.warning(f"Secrets operations should be synchronous, got queued message: {type(message)}")