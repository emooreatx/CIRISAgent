"""API comms endpoints for CIRISAgent (messages, status)."""
import logging
import uuid
from aiohttp import web
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from typing import Any, Dict

logger = logging.getLogger(__name__)

class APICommsRoutes:
    def __init__(self, api_observer: Any, api_adapter: Any) -> None:
        self.api_observer = api_observer
        self.api_adapter = api_adapter

    def register(self, app: web.Application) -> None:
        app.router.add_post('/v1/messages', self._handle_message)
        app.router.add_get('/v1/messages', self._handle_get_messages)
        app.router.add_get('/v1/status', self._handle_status)

    async def _handle_message(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            message = IncomingMessage(
                message_id=data.get("id", str(uuid.uuid4())),
                content=data["content"],
                author_id=data.get("author_id", "api_user"),
                author_name=data.get("author_name", "API User"),
                channel_id=data.get("channel_id", "api"),
            )
            if self.api_observer:
                await self.api_observer.handle_incoming_message(message)
            return web.json_response({"status": "processed", "id": message.message_id})
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return web.json_response({"error": str(e)}, status=400)

    async def _handle_get_messages(self, request: web.Request) -> web.Response:
        try:
            limit = int(request.query.get('limit', 20))
            channel_id = request.query.get('channel_id', 'api')
            
            # Get incoming messages from observer
            incoming_messages = []
            if self.api_observer:
                incoming_messages = await self.api_observer.get_recent_messages(limit * 2)  # Get more to ensure proper sorting
            
            # Get outgoing messages from correlations with timeout to prevent deadlock
            outgoing_messages = []
            try:
                import asyncio
                from functools import partial
                from ciris_engine.persistence.models.correlations import get_correlations_by_type_and_time
                from ciris_engine.schemas.correlation_schemas_v1 import CorrelationType
                from datetime import datetime, timezone, timedelta
                
                # Get correlations for the last 24 hours
                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(hours=24)
                
                # Run correlation query in thread pool with timeout to prevent blocking
                loop = asyncio.get_event_loop()
                correlation_task = loop.run_in_executor(
                    None,
                    partial(
                        get_correlations_by_type_and_time,
                        correlation_type=CorrelationType.SERVICE_INTERACTION,
                        start_time=start_time.isoformat(),
                        end_time=end_time.isoformat(),
                        limit=limit * 2
                    )
                )
                
                # Wait for correlations with timeout to prevent deadlock
                try:
                    correlations = await asyncio.wait_for(correlation_task, timeout=2.0)
                    
                    # Filter for API send_message actions and extract message data
                    for corr in correlations:
                        if (corr.action_type == "send_message" and 
                            corr.service_type == "api" and 
                            corr.request_data and 
                            corr.request_data.get("channel_id") == channel_id):
                            
                            outgoing_messages.append({
                                "id": corr.correlation_id,
                                "content": corr.request_data.get("content", ""),
                                "author_id": "ciris_agent",
                                "author_name": "CIRIS Agent", 
                                "timestamp": corr.created_at,
                                "is_outgoing": True
                            })
                except asyncio.TimeoutError:
                    logger.warning("Correlation query timed out, returning only incoming messages")
                
            except Exception as e:
                logger.warning(f"Could not fetch outgoing message correlations: {e}")
            
            # Mark incoming messages 
            for msg in incoming_messages:
                msg["is_outgoing"] = False
            
            # Combine and sort all messages by timestamp
            all_messages = incoming_messages + outgoing_messages
            
            # Sort by timestamp (handle None timestamps)
            all_messages.sort(key=lambda x: x.get("timestamp") or "1970-01-01T00:00:00Z")
            
            # Return the most recent messages up to the limit
            recent_messages = all_messages[-limit:] if len(all_messages) > limit else all_messages
            
            return web.json_response({"messages": recent_messages})
            
        except Exception as e:
            logger.error(f"Error getting messages: {e}")
            return web.json_response({"error": str(e)}, status=400)

    async def _handle_status(self, request: web.Request) -> web.Response:
        status_data: Dict[str, Any] = {"status": "ok"}
        if self.api_adapter and hasattr(self.api_adapter, 'responses') and self.api_adapter.responses:
            latest_response_id = max(self.api_adapter.responses.keys())
            latest_response = self.api_adapter.responses[latest_response_id]
            status_data["last_response"] = {
                "content": latest_response["content"],
                "timestamp": latest_response["timestamp"]
            }
        return web.json_response(status_data)
