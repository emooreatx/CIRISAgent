"""API agent interaction endpoints - the primary way to communicate with the agent."""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, List, Dict
from aiohttp import web

from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage, FetchedMessage
from ciris_engine.schemas.api_schemas_v1 import MessageResponse, ChannelInfo

logger = logging.getLogger(__name__)


class APIAgentRoutes:
    """Routes for agent interaction - sending messages and managing channels."""
    
    def __init__(self, bus_manager: Any, on_message_callback: Optional[Any] = None) -> None:
        self.bus_manager = bus_manager
        self.on_message = on_message_callback
        self._message_queues: Dict[str, List[IncomingMessage]] = {}
    
    def register(self, app: web.Application) -> None:
        """Register agent interaction routes."""
        # Agent communication
        app.router.add_post('/v1/agent/messages', self._handle_send_message)
        app.router.add_get('/v1/agent/messages/{channel_id}', self._handle_get_messages)
        
        # Channel management
        app.router.add_get('/v1/agent/channels', self._handle_list_channels)
        app.router.add_get('/v1/agent/channels/{channel_id}', self._handle_channel_info)
        
        # Agent status
        app.router.add_get('/v1/agent/status', self._handle_agent_status)
    
    async def _handle_send_message(self, request: web.Request) -> web.Response:
        """Send a message to the agent for processing."""
        try:
            data = await request.json()
            
            # Validate required fields
            content = data.get('content')
            if not content:
                return web.json_response(
                    {"error": "Missing required field: content"},
                    status=400
                )
            
            # Create message with defaults
            channel_id = data.get('channel_id', 'api_default')
            author_id = data.get('author_id', 'api_user')
            author_name = data.get('author_name', 'API User')
            
            msg = IncomingMessage(
                message_id=str(uuid.uuid4()),
                author_id=author_id,
                author_name=author_name,
                content=content,
                channel_id=channel_id,
                reference_message_id=data.get('reference_message_id'),
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            
            # Store in channel queue
            if channel_id not in self._message_queues:
                self._message_queues[channel_id] = []
            self._message_queues[channel_id].append(msg)
            
            # Route to agent via callback
            if self.on_message:
                logger.info(f"Routing message {msg.message_id} to agent")
                await self.on_message(msg)
            else:
                logger.warning("No message handler configured")
            
            response = MessageResponse(
                status="accepted",
                message_id=msg.message_id,
                channel_id=channel_id,
                timestamp=msg.timestamp
            )
            
            return web.json_response(response.model_dump(mode='json'), status=202)
            
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_get_messages(self, request: web.Request) -> web.Response:
        """Get messages from a specific channel."""
        try:
            channel_id = request.match_info['channel_id']
            limit = int(request.query.get('limit', 100))
            after_message_id = request.query.get('after_message_id')
            
            messages = self._message_queues.get(channel_id, [])
            
            # Filter messages after specific ID if requested
            if after_message_id:
                found = False
                filtered_messages = []
                for msg in messages:
                    if found:
                        filtered_messages.append(msg)
                    elif msg.message_id == after_message_id:
                        found = True
                messages = filtered_messages
            
            # Apply limit
            messages = messages[-limit:]
            
            # Convert to response format
            response_messages = [
                {
                    "message_id": msg.message_id,
                    "author_id": msg.author_id,
                    "author_name": msg.author_name,
                    "content": msg.content,
                    "timestamp": msg.timestamp,
                    "reference_message_id": msg.reference_message_id
                }
                for msg in messages
            ]
            
            return web.json_response({
                "channel_id": channel_id,
                "messages": response_messages,
                "count": len(response_messages)
            })
            
        except Exception as e:
            logger.error(f"Error fetching messages: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_list_channels(self, request: web.Request) -> web.Response:
        """List all active channels."""
        try:
            channels = []
            for channel_id, messages in self._message_queues.items():
                if messages:
                    last_message = messages[-1]
                    channels.append({
                        "channel_id": channel_id,
                        "message_count": len(messages),
                        "last_activity": last_message.timestamp
                    })
            
            return web.json_response({
                "channels": channels,
                "count": len(channels)
            })
            
        except Exception as e:
            logger.error(f"Error listing channels: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_channel_info(self, request: web.Request) -> web.Response:
        """Get information about a specific channel."""
        try:
            channel_id = request.match_info['channel_id']
            messages = self._message_queues.get(channel_id, [])
            
            if not messages:
                return web.json_response(
                    {"error": f"Channel {channel_id} not found"},
                    status=404
                )
            
            # Get channel statistics
            authors = set(msg.author_id for msg in messages)
            first_message = messages[0] if messages else None
            last_message = messages[-1] if messages else None
            
            channel_info = ChannelInfo(
                channel_id=channel_id,
                message_count=len(messages),
                unique_authors=len(authors),
                created_at=first_message.timestamp if first_message else "",
                last_activity=last_message.timestamp if last_message else ""
            )
            
            return web.json_response(channel_info.model_dump(mode='json'))
            
        except Exception as e:
            logger.error(f"Error getting channel info: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_agent_status(self, request: web.Request) -> web.Response:
        """Get the agent's current status."""
        try:
            # Get agent status from various sources
            status = {
                "online": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
            # Add processor status if available
            if self.bus_manager and hasattr(self.bus_manager, 'get_processor_status'):
                processor_status = await self.bus_manager.get_processor_status()
                status['processor'] = processor_status
            
            # Add identity info if available
            if self.bus_manager and hasattr(self.bus_manager, 'memory_service'):
                try:
                    # Try to recall agent identity
                    identity_result = await self.bus_manager.recall("AGENT_IDENTITY", scope="identity")
                    if identity_result and hasattr(identity_result, 'nodes') and identity_result.nodes:
                        identity_node = identity_result.nodes[0]
                        status['identity'] = {
                            "agent_id": identity_node.attributes.get('agent_id'),
                            "name": identity_node.attributes.get('name'),
                            "created_at": identity_node.attributes.get('created_at')
                        }
                except Exception as e:
                    logger.debug(f"Could not fetch agent identity: {e}")
            
            # Add active channel count
            status['active_channels'] = len([
                ch for ch, msgs in self._message_queues.items() if msgs
            ])
            
            return web.json_response(status)
            
        except Exception as e:
            logger.error(f"Error getting agent status: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)