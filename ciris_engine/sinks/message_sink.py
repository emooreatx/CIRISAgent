"""
Message sink implementation for communication-related actions.
"""

import logging
from typing import Dict, List, Optional, Any

from .action_types import ActionType, ActionMessage, SendMessageAction, FetchMessagesAction
from .base_sink import BaseMultiServiceSink
from ..protocols.services import CommunicationService

logger = logging.getLogger(__name__)


class MultiServiceMessageSink(BaseMultiServiceSink):
    """Specialized sink for communication-related actions"""
    
    @property
    def service_routing(self) -> Dict[ActionType, str]:
        return {
            ActionType.SEND_MESSAGE: 'communication',
            ActionType.FETCH_MESSAGES: 'communication',
        }
    
    @property
    def capability_map(self) -> Dict[ActionType, List[str]]:
        return {
            ActionType.SEND_MESSAGE: ['send_message'],
            ActionType.FETCH_MESSAGES: ['fetch_messages'],
        }
    
    async def _execute_action_on_service(self, service: CommunicationService, action: ActionMessage):
        """Execute communication action on service"""
        if action.type == ActionType.SEND_MESSAGE:
            success = await service.send_message(action.channel_id, action.content)
            if success:
                logger.info(f"Message sent via {type(service).__name__} to {action.channel_id}")
            else:
                logger.warning(f"Failed to send message via {type(service).__name__}")
        elif action.type == ActionType.FETCH_MESSAGES:
            messages = await service.fetch_messages(action.channel_id, action.limit)
            logger.info(f"Fetched {len(messages) if messages else 0} messages from {action.channel_id}")
            return messages
    
    async def send_message(self, handler_name: str, channel_id: str, content: str, metadata: Optional[Dict] = None) -> bool:
        """Convenience method to send a message"""
        action = SendMessageAction(
            handler_name=handler_name,
            metadata=metadata or {},
            channel_id=channel_id,
            content=content
        )
        return await self.enqueue_action(action)
