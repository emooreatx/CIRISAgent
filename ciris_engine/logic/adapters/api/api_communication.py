"""
Communication service for API adapter.
"""
import logging
from typing import Any, Optional, Dict, List
from datetime import datetime, timezone
import asyncio

from ciris_engine.protocols.services.governance.communication import CommunicationServiceProtocol

logger = logging.getLogger(__name__)


class APICommunicationService(CommunicationServiceProtocol):
    """Communication service for API responses."""
    
    def __init__(self) -> None:
        """Initialize API communication service."""
        self._response_queue: asyncio.Queue = asyncio.Queue()
        self._websocket_clients: Dict[str, Any] = {}
        self._is_started = False
    
    async def send_message(self, channel_id: str, content: str) -> bool:
        """Send message through API response or WebSocket."""
        try:
            # Create a "speak" correlation for this outgoing message
            from ciris_engine.logic import persistence
            from ciris_engine.schemas.telemetry.core import ServiceCorrelation, ServiceCorrelationStatus
            from ciris_engine.schemas.telemetry.core import ServiceRequestData, ServiceResponseData
            import uuid
            
            correlation_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            
            # Create correlation for the outgoing message
            correlation = ServiceCorrelation(
                correlation_id=correlation_id,
                service_type="api",
                handler_name="APIAdapter",
                action_type="speak",
                request_data=ServiceRequestData(
                    service_type="api",
                    method_name="speak",
                    channel_id=channel_id,
                    parameters={
                        "content": content,
                        "channel_id": channel_id
                    },
                    request_timestamp=now
                ),
                response_data=ServiceResponseData(
                    success=True,
                    result_summary="Message sent",
                    execution_time_ms=0,
                    response_timestamp=now
                ),
                status=ServiceCorrelationStatus.COMPLETED,
                created_at=now,
                updated_at=now,
                timestamp=now
            )
            
            # Get time service if available (passed from adapter)
            time_service = getattr(self, '_time_service', None)
            persistence.add_correlation(correlation, time_service)
            logger.debug(f"Created speak correlation for channel {channel_id}")
            # If it's a WebSocket channel, send through WebSocket
            if channel_id and channel_id.startswith("ws:"):
                client_id = channel_id[3:]  # Remove "ws:" prefix
                if client_id in self._websocket_clients:
                    ws = self._websocket_clients[client_id]
                    await ws.send_json({
                        "type": "message",
                        "data": {
                            "content": content,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                    })
                    return True
                else:
                    logger.warning(f"WebSocket client not found: {client_id}")
                    return False
            
            # Otherwise, queue for HTTP response
            await self._response_queue.put({"channel_id": channel_id, "content": content})
            
            # Check if there's a waiting interact request for this channel
            if channel_id and channel_id.startswith("api_"):
                # Try to find the message ID for this channel
                try:
                    # Access the app state through the runtime's adapter
                    if hasattr(self, '_app_state'):
                        message_channel_map = getattr(self._app_state, 'message_channel_map', {})
                        message_id = message_channel_map.get(channel_id)
                        if message_id:
                            from ciris_engine.logic.adapters.api.routes.agent import notify_interact_response
                            await notify_interact_response(message_id, content)
                            logger.info(f"Notified interact response for message {message_id} in channel {channel_id}")
                            # Clean up the mapping
                            del message_channel_map[channel_id]
                except Exception as e:
                    logger.debug(f"Could not notify interact response: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    async def get_response(self, timeout: float = 30.0) -> Optional[Any]:
        """Get queued response for HTTP requests."""
        try:
            return await asyncio.wait_for(
                self._response_queue.get(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            return None
    
    def register_websocket(self, client_id: str, websocket: Any) -> None:
        """Register a WebSocket client."""
        self._websocket_clients[client_id] = websocket
        logger.info(f"WebSocket client registered: {client_id}")
    
    def unregister_websocket(self, client_id: str) -> None:
        """Unregister a WebSocket client."""
        if client_id in self._websocket_clients:
            del self._websocket_clients[client_id]
            logger.info(f"WebSocket client unregistered: {client_id}")
    
    async def broadcast(
        self,
        message: str,
        channel: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Broadcast message to all WebSocket clients."""
        sent_count = 0
        
        data = {
            "type": "broadcast",
            "channel": channel or "general",
            "data": {
                "content": message,
                "metadata": metadata or {},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        
        # Send to all connected WebSocket clients
        disconnected = []
        for client_id, ws in self._websocket_clients.items():
            try:
                await ws.send_json(data)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to send to {client_id}: {e}")
                disconnected.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected:
            self.unregister_websocket(client_id)
        
        return sent_count
    
    def get_available_channels(self) -> List[str]:
        """Get list of available channels."""
        channels = ["http"]  # Always available for HTTP responses
        
        # Add WebSocket channels
        channels.extend([f"ws:{client_id}" for client_id in self._websocket_clients])
        
        return channels
    
    async def is_channel_available(self, channel_id: str) -> bool:
        """Check if a channel is available."""
        if channel_id == "http":
            return True
        
        if channel_id.startswith("ws:"):
            client_id = channel_id[3:]
            return client_id in self._websocket_clients
        
        return False
    
    async def fetch_messages(
        self,
        channel_id: str,
        *,
        limit: int = 50,
        before: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve messages from a channel using the correlations database."""
        from ciris_engine.logic.persistence import get_correlations_by_channel
        from ciris_engine.schemas.runtime.messages import FetchedMessage
        
        try:
            # Get correlations for this channel
            correlations = get_correlations_by_channel(
                channel_id=channel_id,
                limit=limit,
                before=before
            )
            
            messages = []
            for corr in correlations:
                # Extract message data from correlation
                if corr.action_type == "speak" and corr.request_data:
                    # This is an outgoing message from the agent
                    content = ""
                    # Handle both dict and Pydantic model cases
                    if isinstance(corr.request_data, dict):
                        params = corr.request_data.get("parameters", {})
                        content = params.get("content", "")
                    elif hasattr(corr.request_data, 'parameters') and corr.request_data.parameters:
                        content = corr.request_data.parameters.get("content", "")
                    
                    messages.append({
                        "message_id": corr.correlation_id,
                        "author_id": "ciris",  # Agent messages
                        "author_name": "CIRIS",
                        "content": content,
                        "timestamp": corr.timestamp or corr.created_at,
                        "channel_id": channel_id,
                        "is_agent_message": True
                    })
                elif corr.action_type == "observe" and corr.request_data:
                    # This is an incoming message from a user
                    content = ""
                    author_id = "unknown"
                    author_name = "User"
                    
                    # Handle both dict and Pydantic model cases
                    if isinstance(corr.request_data, dict):
                        params = corr.request_data.get("parameters", {})
                        content = params.get("content", "")
                        author_id = params.get("author_id", "unknown")
                        author_name = params.get("author_name", "User")
                    elif hasattr(corr.request_data, 'parameters') and corr.request_data.parameters:
                        params = corr.request_data.parameters
                        content = params.get("content", "")
                        author_id = params.get("author_id", "unknown")
                        author_name = params.get("author_name", "User")
                    
                    messages.append({
                        "message_id": corr.correlation_id,
                        "author_id": author_id,
                        "author_name": author_name,
                        "content": content,
                        "timestamp": corr.timestamp or corr.created_at,
                        "channel_id": channel_id,
                        "is_agent_message": False
                    })
            
            # Sort by timestamp
            messages.sort(key=lambda m: m["timestamp"])
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to fetch messages from correlations for channel {channel_id}: {e}")
            return []
    
    async def start(self) -> None:
        """Start the communication service."""
        self._is_started = True
        logger.info("API communication service started")
    
    async def stop(self) -> None:
        """Stop the communication service."""
        self._is_started = False
        # Clear any pending responses
        while not self._response_queue.empty():
            try:
                self._response_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        logger.info("API communication service stopped")
    
    async def is_healthy(self) -> bool:
        """Check if the service is healthy."""
        return self._is_started
    
    def get_status(self) -> Dict[str, Any]:
        """Get the service status."""
        return {
            "service": "APICommunicationService",
            "started": self._is_started,
            "queued_responses": self._response_queue.qsize(),
            "websocket_clients": len(self._websocket_clients)
        }
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get the service capabilities."""
        return {
            "service": "APICommunicationService",
            "capabilities": {
                "http_responses": True,
                "websocket_broadcast": True,
                "message_queueing": True,
                "channel_based_routing": True
            }
        }