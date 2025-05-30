"""
Deferral sink implementation for deferral-related actions.
"""

import logging
from typing import Dict, List, Optional, Any

from .action_types import ActionType, SendDeferralAction, ActionMessage
from .base_sink import BaseMultiServiceSink
from ..protocols.services import WiseAuthorityService

logger = logging.getLogger(__name__)


class MultiServiceDeferralSink(BaseMultiServiceSink):
    """Specialized sink for deferral actions that routes to WiseAuthorityService."""
    
    @property
    def service_routing(self) -> Dict[ActionType, str]:
        return {
            ActionType.SEND_DEFERRAL: 'wise_authority',
        }
    
    @property
    def capability_map(self) -> Dict[ActionType, List[str]]:
        return {
            ActionType.SEND_DEFERRAL: ['send_deferral'],
        }
    
    async def _execute_action_on_service(self, service: WiseAuthorityService, action: SendDeferralAction):
        """Execute deferral action on WiseAuthorityService"""
        success = await service.send_deferral(action.thought_id, action.reason)
        if success:
            logger.info(f"Deferral sent via {type(service).__name__} for thought {action.thought_id}")
        else:
            logger.warning(f"Failed to send deferral via {type(service).__name__}")
    
    async def send_deferral(self, handler_name: str, thought_id: str, reason: str, metadata: Optional[Dict] = None) -> bool:
        """Convenience method to send a deferral"""
        action = SendDeferralAction(
            handler_name=handler_name,
            metadata=metadata or {},
            thought_id=thought_id,
            reason=reason
        )
        return await self.enqueue_action(action)
