"""
Wise Authority message bus - handles all WA service operations
"""

import logging
from typing import Optional, TYPE_CHECKING

from ciris_engine.schemas.runtime.enums import ServiceType
from ciris_engine.schemas.services.context import GuidanceContext, DeferralContext
from ciris_engine.protocols.services import WiseAuthorityService
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from .base_bus import BaseBus, BusMessage

if TYPE_CHECKING:
    from ciris_engine.logic.registries.base import ServiceRegistry

logger = logging.getLogger(__name__)

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
        """Send a deferral to ALL wise authority services (broadcast)"""
        # Get ALL services with send_deferral capability
        # Since we want to broadcast to all WA services, we need to get them all
        # The registry returns services based on priority, so we'll get multiple if available
        services = []
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["send_deferral"]
        )
        if service:
            services.append(service)

        if not services:
            logger.info(f"No wise authority service available for {handler_name}")
            return False

        # Track if any service successfully received the deferral
        any_success = False

        try:
            # Convert DeferralContext to DeferralRequest
            from ciris_engine.schemas.services.authority_core import DeferralRequest

            # Handle defer_until - it may be None
            defer_until = None
            if context.defer_until:
                # If it's already a datetime, use it directly
                if hasattr(context.defer_until, 'isoformat'):
                    defer_until = context.defer_until
                else:
                    # Try to parse as string
                    from datetime import datetime
                    try:
                        # Handle both 'Z' and '+00:00' formats
                        defer_str = str(context.defer_until)
                        if defer_str.endswith('Z'):
                            defer_str = defer_str[:-1] + '+00:00'
                        defer_until = datetime.fromisoformat(defer_str)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse defer_until date '{context.defer_until}': {type(e).__name__}: {str(e)} - Task will be deferred to default time")
                        defer_until = self._time_service.now()
            else:
                # Default to now + 1 hour if not specified
                from datetime import timedelta
                defer_until = self._time_service.now() + timedelta(hours=1)

            deferral_request = DeferralRequest(
                task_id=context.task_id,
                thought_id=context.thought_id,
                reason=context.reason,
                defer_until=defer_until,
                context=context.metadata  # Map metadata to context
            )

            # Broadcast to ALL registered WA services
            logger.info(f"Broadcasting deferral to {len(services)} wise authority service(s)")
            for service in services:
                try:
                    result = await service.send_deferral(deferral_request)
                    if result:
                        any_success = True
                        logger.debug(f"Successfully sent deferral to WA service: {service.__class__.__name__}")
                except Exception as e:
                    logger.warning(f"Failed to send deferral to WA service {service.__class__.__name__}: {e}")
                    continue

            return any_success
        except Exception as e:
            logger.error(f"Failed to prepare deferral request: {e}", exc_info=True)
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
