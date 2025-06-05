"""API comms endpoints for CIRISAgent (messages, status)."""
import logging
import uuid
from aiohttp import web
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from typing import Any

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
            if self.api_observer:
                messages = await self.api_observer.get_recent_messages(limit)
                return web.json_response({"messages": messages})
            else:
                return web.json_response({"messages": []})
        except Exception as e:
            logger.error(f"Error getting messages: {e}")
            return web.json_response({"error": str(e)}, status=400)

    async def _handle_status(self, request: web.Request) -> web.Response:
        status_data = {"status": "ok"}
        if self.api_adapter and hasattr(self.api_adapter, 'responses') and self.api_adapter.responses:
            latest_response_id = max(self.api_adapter.responses.keys())
            latest_response = self.api_adapter.responses[latest_response_id]
            status_data["last_response"] = {
                "content": latest_response["content"],
                "timestamp": latest_response["timestamp"]
            }
        return web.json_response(status_data)
