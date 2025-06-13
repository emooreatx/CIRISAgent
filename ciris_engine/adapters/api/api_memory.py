"""API memory endpoints for CIRISAgent, using the multi_service_sink for persistence-backed memory service."""
import logging
from aiohttp import web
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpStatus
from typing import Any

logger = logging.getLogger(__name__)

class APIMemoryRoutes:
    def __init__(self, multi_service_sink: Any) -> None:
        self.multi_service_sink = multi_service_sink

    def register(self, app: web.Application) -> None:
        app.router.add_get('/v1/memory/scopes', self._handle_memory_scopes)
        app.router.add_get('/v1/memory/{scope}/entries', self._handle_memory_entries)
        app.router.add_post('/v1/memory/{scope}/store', self._handle_memory_store)
        app.router.add_post('/v1/memory/search', self._handle_memory_search)
        app.router.add_post('/v1/memory/recall', self._handle_memory_recall)
        app.router.add_delete('/v1/memory/{scope}/{node_id}', self._handle_memory_forget)
        app.router.add_get('/v1/memory/timeseries', self._handle_memory_timeseries)

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
            if memory_service is None:
                # Service is not available at all
                logger.error("Memory service is not available")
                return web.json_response({"error": "Memory service not available"}, status=500)
            
            if hasattr(memory_service, 'list_entries'):
                entries = await memory_service.list_entries(scope)
            else:
                entries = []
            return web.json_response({"entries": entries})
        except AttributeError as e:
            # When memory_service is completely unavailable
            logger.error(f"Memory service unavailable: {e}")
            return web.json_response({"error": "Memory service not available"}, status=500)
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
            # Convert string scope to GraphScope enum
            try:
                graph_scope = GraphScope(scope)
            except ValueError:
                graph_scope = GraphScope.LOCAL  # Fallback to LOCAL scope
            node = GraphNode(id=key, type=NodeType.CONCEPT, scope=graph_scope, attributes={"value": value})
            # Use the multi_service_sink to memorize
            result = await self.multi_service_sink.memorize(node)
            if hasattr(result, "status") and result.status == MemoryOpStatus.OK:
                return web.json_response({"result": "ok"})
            return web.json_response({"error": getattr(result, "reason", "Unknown error")}, status=500)
        except Exception as e:
            logger.error(f"Error in memory store: {e}")
            return web.json_response({"error": str(e)}, status=400)

    async def _handle_memory_search(self, request: web.Request) -> web.Response:
        """Search memories by query."""
        try:
            data = await request.json()
            query = data.get("query", "")
            scope = data.get("scope", "local")
            limit = data.get("limit", 10)
            
            memory_service = getattr(self.multi_service_sink, 'memory_service', None)
            if memory_service and hasattr(memory_service, 'search'):
                results = await memory_service.search(query, scope, limit)
                return web.json_response({"results": results})
            else:
                return web.json_response({"error": "Memory search not available"}, status=500)
        except Exception as e:
            logger.error(f"Error in memory search: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_memory_recall(self, request: web.Request) -> web.Response:
        """Recall memories by context."""
        try:
            data = await request.json()
            context = data.get("context", "")
            scope = data.get("scope", "local")
            max_results = data.get("max_results", 5)
            
            memory_service = getattr(self.multi_service_sink, 'memory_service', None)
            if memory_service and hasattr(memory_service, 'recall'):
                memories = await memory_service.recall(context, scope, max_results)
                return web.json_response({"memories": memories})
            else:
                return web.json_response({"error": "Memory recall not available"}, status=400)
        except Exception as e:
            logger.error(f"Error in memory recall: {e}")
            return web.json_response({"error": str(e)}, status=400)

    async def _handle_memory_forget(self, request: web.Request) -> web.Response:
        """Forget a specific memory node."""
        try:
            scope = request.match_info.get('scope')
            node_id = request.match_info.get('node_id')
            
            memory_service = getattr(self.multi_service_sink, 'memory_service', None)
            if memory_service and hasattr(memory_service, 'forget'):
                result = await memory_service.forget(scope, node_id)
                return web.json_response(result)
            else:
                return web.json_response({"error": "Memory service not available"}, status=500)
        except Exception as e:
            logger.error(f"Error in memory forget: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_memory_timeseries(self, request: web.Request) -> web.Response:
        """Get time-series memory data."""
        try:
            scope = request.query.get('scope', 'session')
            limit = int(request.query.get('limit', 100))
            
            memory_service = getattr(self.multi_service_sink, 'memory_service', None)
            if memory_service and hasattr(memory_service, 'get_timeseries'):
                results = await memory_service.get_timeseries(scope, limit)
                return web.json_response(results)
            else:
                return web.json_response({"error": "Memory timeseries not available"}, status=500)
        except Exception as e:
            logger.error(f"Error in memory timeseries: {e}")
            return web.json_response({"error": str(e)}, status=500)
