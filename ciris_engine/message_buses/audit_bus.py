"""
Audit message bus - handles all audit service operations
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from ciris_engine.schemas.foundational_schemas_v1 import ServiceType
from ciris_engine.schemas.capability_schemas_v1 import AuditCapabilities
from ciris_engine.protocols.services import AuditService
from .base_bus import BaseBus, BusMessage

logger = logging.getLogger(__name__)


class AuditBus(BaseBus):
    """
    Message bus for all audit operations.
    
    Handles:
    - log_event
    - get_audit_trail
    """
    
    def __init__(self, service_registry: Any):
        super().__init__(
            service_type=ServiceType.AUDIT,
            service_registry=service_registry
        )
    
    async def log_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        handler_name: str
    ) -> None:
        """Log an audit event"""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=[AuditCapabilities.LOG_EVENT]
        )
        
        if not service:
            logger.warning(f"No audit service available for {handler_name}")
            return
            
        try:
            await service.log_event(
                event_type=event_type,
                event_data=event_data
            )
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}", exc_info=True)
    
    async def get_audit_trail(
        self,
        entity_id: str,
        handler_name: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get audit trail for an entity"""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=[AuditCapabilities.GET_AUDIT_TRAIL]
        )
        
        if not service:
            logger.error(f"No audit service available for {handler_name}")
            return []
            
        try:
            result = await service.get_audit_trail(entity_id, limit)
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"Failed to get audit trail: {e}", exc_info=True)
            return []
    
    async def _process_message(self, message: BusMessage) -> None:
        """Process an audit message - currently all audit operations are synchronous"""
        logger.warning(f"Audit operations should be synchronous, got queued message: {type(message)}")