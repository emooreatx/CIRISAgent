"""API memory endpoints for CIRISAgent, using the multi_service_sink for persistence-backed memory service."""
import logging
from aiohttp import web
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpStatus
from typing import Any, List

logger = logging.getLogger(__name__)

class APIMemoryRoutes:
    def __init__(self, multi_service_sink: Any) -> None:
        self.multi_service_sink = multi_service_sink

    def register(self, app: web.Application) -> None:
        app.router.add_get('/v1/memory/scopes', self._handle_memory_scopes)
        app.router.add_get('/v1/memory/{scope}/entries', self._handle_memory_entries)
        app.router.add_post('/v1/memory/{scope}/store', self._handle_memory_store)

    async def _handle_memory_scopes(self, request: web.Request) -> web.Response:
        try:
            # Use the memory service from the multi_service_sink
            memory_service = getattr(self.multi_service_sink, 'memory_service', None)
            if memory_service and hasattr(memory_service, 'list_scopes'):
                scopes = await memory_service.list_scopes()
            else:
                # Fallback: try to infer from available nodes
                scopes = [s.value for s in GraphScope]
            return web.json_response({"scopes": scopes})
        except Exception as e:
            logger.error(f"Error in memory scopes: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_memory_entries(self, request: web.Request) -> web.Response:
        scope = request.match_info.get('scope')
        try:
            memory_service = getattr(self.multi_service_sink, 'memory_service', None)
            if memory_service and hasattr(memory_service, 'list_entries'):
                entries = await memory_service.list_entries(scope)
            else:
                entries: List[Any] = []
            return web.json_response({"entries": entries})
        except Exception as e:
            logger.error(f"Error in memory entries: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_memory_store(self, request: web.Request) -> web.Response:
        scope = request.match_info.get('scope')
        try:
            data = await request.json()
            key = data.get("key")
            value = data.get("value")
            if not key:
                return web.json_response({"error": "Missing key"}, status=400)
            node = GraphNode(id=key, type=NodeType.CONCEPT, scope=GraphScope(scope), attributes={"value": value})
            # Use the multi_service_sink to memorize
            result = await self.multi_service_sink.memorize(node)
            if hasattr(result, "status") and result.status == MemoryOpStatus.OK:
                return web.json_response({"result": "ok"})
            return web.json_response({"error": getattr(result, "reason", "Unknown error")}, status=500)
        except Exception as e:
            logger.error(f"Error in memory store: {e}")
            return web.json_response({"error": str(e)}, status=400)
