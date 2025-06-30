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
        """Retrieve messages from a channel - not implemented for API."""
        # API doesn't store messages, they're handled by request/response
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