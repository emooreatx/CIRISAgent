"""
Communication message bus - handles all communication service operations
"""

import logging
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass

from ciris_engine.schemas.foundational_schemas_v1 import ServiceType, FetchedMessage
from ciris_engine.protocols.services import CommunicationService
from ciris_engine.utils.time_utils import utc_now
from .base_bus import BaseBus, BusMessage

logger = logging.getLogger(__name__)


@dataclass
class SendMessageRequest(BusMessage):
    """Request to send a message"""
    channel_id: str
    content: str


@dataclass  
class FetchMessagesRequest(BusMessage):
    """Request to fetch messages"""
    channel_id: str
    limit: int = 100


class CommunicationBus(BaseBus[CommunicationService]):
    """
    Message bus for all communication operations.
    
    Handles:
    - send_message
    - fetch_messages
    """
    
    def __init__(self, service_registry: Any):
        super().__init__(
            service_type=ServiceType.COMMUNICATION,
            service_registry=service_registry
        )
    
    async def send_message(
        self,
        channel_id: str,
        content: str,
        handler_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send a message to a channel.
        
        This is async and returns immediately after queuing.
        """
        message = SendMessageRequest(
            id=str(uuid.uuid4()),
            handler_name=handler_name,
            timestamp=utc_now(),
            metadata=metadata or {},
            channel_id=channel_id,
            content=content
        )
        
        success = await self._enqueue(message)
        if success:
            logger.debug(f"Queued send_message for channel {channel_id}")
        return success
    
    async def send_message_sync(
        self,
        channel_id: str,
        content: str,
        handler_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send a message synchronously (wait for completion).
        
        This bypasses the queue for immediate operations.
        """
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["send_message"]
        )
        
        if not service:
            logger.error(f"No communication service available for {handler_name}")
            return False
            
        try:
            result = await service.send_message(channel_id, content)
            return bool(result)
        except Exception as e:
            logger.error(f"Failed to send message: {e}", exc_info=True)
            return False
    
    async def fetch_messages(
        self,
        channel_id: str,
        limit: int,
        handler_name: str
    ) -> List[FetchedMessage]:
        """
        Fetch messages from a channel.
        
        This is always synchronous as we need the result.
        """
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["fetch_messages"]
        )
        
        if not service:
            logger.error(f"No communication service available for {handler_name}")
            return []
            
        try:
            messages = await service.fetch_messages(channel_id, limit)
            return list(messages) if messages else []
        except Exception as e:
            logger.error(f"Failed to fetch messages: {e}", exc_info=True)
            return []
    
    async def _process_message(self, message: BusMessage) -> None:
        """Process a communication message"""
        if isinstance(message, SendMessageRequest):
            await self._process_send_message(message)
        elif isinstance(message, FetchMessagesRequest):
            # Fetch is always sync, shouldn't be in queue
            logger.warning(f"FetchMessagesRequest in queue - this shouldn't happen")
        else:
            logger.error(f"Unknown message type: {type(message)}")
    
    async def _process_send_message(self, request: SendMessageRequest) -> None:
        """Process a send message request"""
        service = await self.get_service(
            handler_name=request.handler_name,
            required_capabilities=["send_message"]
        )
        
        if not service:
            raise RuntimeError(
                f"No communication service available for {request.handler_name}"
            )
        
        # Send the message
        success = await service.send_message(
            request.channel_id,
            request.content
        )
        
        if success:
            logger.debug(
                f"Successfully sent message to {request.channel_id} "
                f"via {type(service).__name__}"
            )
        else:
            logger.warning(
                f"Failed to send message to {request.channel_id} "
                f"via {type(service).__name__}"
            )