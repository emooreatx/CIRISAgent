"""
Wise Authority message bus - handles all WA service operations
"""

import logging
from typing import Optional, TYPE_CHECKING
from ciris_engine.schemas.runtime.enums import ServiceType

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ciris_engine.logic.registries.base import ServiceRegistry
from ciris_engine.schemas.services.context import GuidanceContext, DeferralContext
from ciris_engine.protocols.services import WiseAuthorityService
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from .base_bus import BaseBus, BusMessage

class WiseBus(BaseBus[WiseAuthorityService]):
    """
    Message bus for all wise authority operations.
    
    Handles:
    - send_deferral
    - fetch_guidance
    """
    
    def __init__(self, service_registry: "ServiceRegistry", time_service: TimeServiceProtocol):
        super().__init__(
            service_type=ServiceType.WISE_AUTHORITY,
            service_registry=service_registry
        )
        self._time_service = time_service
    
    async def send_deferral(
        self,
        context: DeferralContext,
        handler_name: str
    ) -> bool:
        """Send a deferral to wise authority"""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["send_deferral"]
        )
        
        if not service:
            logger.error(f"No wise authority service available for {handler_name}")
            return False
            
        try:
            result = await service.send_deferral(context)
            return bool(result)
        except Exception as e:
            logger.error(f"Failed to send deferral: {e}", exc_info=True)
            return False
    
    async def fetch_guidance(
        self,
        context: GuidanceContext,
        handler_name: str
    ) -> Optional[str]:
        """Fetch guidance from wise authority"""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["fetch_guidance"]
        )
        
        if not service:
            logger.debug(f"No wise authority service available for {handler_name}")
            return None
            
        try:
            result = await service.fetch_guidance(context)
            return str(result) if result is not None else None
        except Exception as e:
            logger.error(f"Failed to fetch guidance: {e}", exc_info=True)
            return None
    
    async def request_review(
        self,
        review_type: str,
        review_data: dict,
        handler_name: str
    ) -> bool:
        """Request a review from wise authority (e.g., for identity variance)"""
        # Create a deferral context for the review
        context = DeferralContext(
            thought_id=f"review_{review_type}_{handler_name}",
            task_id=f"review_task_{review_type}",
            reason=f"Review requested: {review_type}",
            defer_until=None,
            priority=None,
            metadata={"review_data": str(review_data), "handler_name": handler_name}
        )
        
        return await self.send_deferral(context, handler_name)
    
    async def _process_message(self, message: BusMessage) -> None:
        """Process a wise authority message - currently all WA operations are synchronous"""
        logger.warning(f"Wise authority operations should be synchronous, got queued message: {type(message)}")