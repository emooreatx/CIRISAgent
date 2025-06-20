"""API memory endpoints - observability into the agent's graph memory.

This module provides read-only visibility into the agent's memory graph.
Memory modifications happen through the agent's MEMORIZE/FORGET actions,
not through direct API manipulation.
"""
import logging
from aiohttp import web
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpStatus
from typing import Any

logger = logging.getLogger(__name__)

class APIMemoryRoutes:
    def __init__(self, bus_manager: Any) -> None:
        self.bus_manager = bus_manager

    def register(self, app: web.Application) -> None:
        # Graph memory observability (read-only)
        app.router.add_get('/v1/memory/graph/nodes', self._handle_graph_nodes)
        app.router.add_get('/v1/memory/graph/nodes/{node_id}', self._handle_node_details)
        app.router.add_get('/v1/memory/graph/relationships', self._handle_relationships)
        app.router.add_get('/v1/memory/graph/search', self._handle_graph_search)
        
        # Memory scopes and organization
        app.router.add_get('/v1/memory/scopes', self._handle_memory_scopes)
        app.router.add_get('/v1/memory/scopes/{scope}/nodes', self._handle_scope_nodes)
        
        # Time-based memory queries
        app.router.add_get('/v1/memory/timeseries', self._handle_memory_timeseries)
        app.router.add_get('/v1/memory/timeline', self._handle_memory_timeline)
        
        # Agent identity (special case - always visible)
        app.router.add_get('/v1/memory/identity', self._handle_agent_identity)

    async def _handle_memory_scopes(self, request: web.Request) -> web.Response:
        try:
            # Use the memory service from the bus_manager
            memory_service = getattr(self.bus_manager, 'memory_service', None)
            if memory_service and hasattr(memory_service, 'list_scopes'):
                scopes = await memory_service.list_scopes()
            else:
                # Fallback: try to infer from available nodes
                scopes = [s.value for s in GraphScope]
            return web.json_response({"scopes": scopes})
        except Exception as e:
            logger.error(f"Error in memory scopes: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_relationships(self, request: web.Request) -> web.Response:
        """Get memory relationships/edges in the graph."""
        try:
            # Parse query parameters
            relationship_type = request.query.get('type')
            source_id = request.query.get('source')
            target_id = request.query.get('target')
            limit = int(request.query.get('limit', 100))
            
            memory_service = getattr(self.bus_manager, 'memory_service', None)
            if not memory_service:
                return web.json_response({"error": "Memory service not available"}, status=503)
            
            # Get relationships
            relationships = []
            if hasattr(memory_service, 'list_relationships'):
                filters = {}
                if relationship_type:
                    filters['type'] = relationship_type
                if source_id:
                    filters['source_id'] = source_id
                if target_id:
                    filters['target_id'] = target_id
                    
                relationships = await memory_service.list_relationships(filters=filters, limit=limit)
            
            # Format response
            return web.json_response({
                "relationships": relationships,
                "count": len(relationships)
            })
        except Exception as e:
            logger.error(f"Error getting relationships: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_graph_nodes(self, request: web.Request) -> web.Response:
        """Get graph nodes with optional filtering."""
        try:
            # Parse query parameters
            node_type = request.query.get('type')
            scope = request.query.get('scope')
            limit = int(request.query.get('limit', 100))
            offset = int(request.query.get('offset', 0))
            
            # Get nodes from memory service
            memory_service = getattr(self.bus_manager, 'memory_service', None)
            if not memory_service:
                return web.json_response({"error": "Memory service not available"}, status=503)
            
            # Build filter criteria
            filters = {}
            if node_type:
                filters['node_type'] = node_type
            if scope:
                filters['scope'] = scope
            
            # Get nodes
            nodes = []
            if hasattr(memory_service, 'list_nodes'):
                nodes = await memory_service.list_nodes(filters=filters, limit=limit, offset=offset)
            
            # Format for response
            return web.json_response({
                "nodes": [{
                    "id": node.id,
                    "type": node.type.value if hasattr(node.type, 'value') else str(node.type),
                    "scope": node.scope.value if hasattr(node.scope, 'value') else str(node.scope),
                    "attributes": node.attributes,
                    "created_at": getattr(node, 'created_at', None),
                    "updated_at": getattr(node, 'updated_at', None)
                } for node in nodes],
                "count": len(nodes),
                "filters": filters
            })
        except Exception as e:
            logger.error(f"Error getting graph nodes: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_graph_search(self, request: web.Request) -> web.Response:
        """Search the memory graph."""
        try:
            # Get search parameters from query string (GET request)
            query = request.query.get('q', '')
            scope = request.query.get('scope')
            node_type = request.query.get('type')
            limit = int(request.query.get('limit', 20))
            
            if not query:
                return web.json_response({"error": "Query parameter 'q' is required"}, status=400)
            
            memory_service = getattr(self.bus_manager, 'memory_service', None)
            if not memory_service:
                return web.json_response({"error": "Memory service not available"}, status=503)
            
            # Search the graph
            results = []
            if hasattr(memory_service, 'search_graph'):
                search_params = {
                    'query': query,
                    'limit': limit
                }
                if scope:
                    search_params['scope'] = scope
                if node_type:
                    search_params['node_type'] = node_type
                    
                results = await memory_service.search_graph(**search_params)
            
            # Format results
            return web.json_response({
                "query": query,
                "results": [{
                    "id": result.get('id'),
                    "type": result.get('type'),
                    "scope": result.get('scope'),
                    "relevance": result.get('relevance', 1.0),
                    "snippet": result.get('snippet', ''),
                    "attributes": result.get('attributes', {})
                } for result in results],
                "count": len(results)
            })
        except Exception as e:
            logger.error(f"Error in graph search: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_scope_nodes(self, request: web.Request) -> web.Response:
        """Get all nodes within a specific scope."""
        try:
            scope = request.match_info['scope']
            limit = int(request.query.get('limit', 100))
            offset = int(request.query.get('offset', 0))
            
            memory_service = getattr(self.bus_manager, 'memory_service', None)
            if not memory_service:
                return web.json_response({"error": "Memory service not available"}, status=503)
            
            # Get nodes in scope
            nodes = []
            if hasattr(memory_service, 'list_nodes'):
                nodes = await memory_service.list_nodes(
                    filters={'scope': scope},
                    limit=limit,
                    offset=offset
                )
            
            # Format response
            return web.json_response({
                "scope": scope,
                "nodes": [{
                    "id": node.id,
                    "type": node.type.value if hasattr(node.type, 'value') else str(node.type),
                    "attributes": node.attributes,
                    "created_at": getattr(node, 'created_at', None)
                } for node in nodes],
                "count": len(nodes),
                "total": getattr(memory_service, f'{scope}_node_count', len(nodes))
            })
        except Exception as e:
            logger.error(f"Error getting scope nodes: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_node_details(self, request: web.Request) -> web.Response:
        """Get detailed information about a specific node."""
        try:
            node_id = request.match_info['node_id']
            
            memory_service = getattr(self.bus_manager, 'memory_service', None)
            if not memory_service:
                return web.json_response({"error": "Memory service not available"}, status=503)
            
            # Get node details
            node = None
            relationships = []
            
            if hasattr(memory_service, 'get_node'):
                node = await memory_service.get_node(node_id)
            
            if not node:
                return web.json_response({"error": f"Node {node_id} not found"}, status=404)
            
            # Get relationships if available
            if hasattr(memory_service, 'get_node_relationships'):
                relationships = await memory_service.get_node_relationships(node_id)
            
            # Format response
            return web.json_response({
                "node": {
                    "id": node.id,
                    "type": node.type.value if hasattr(node.type, 'value') else str(node.type),
                    "scope": node.scope.value if hasattr(node.scope, 'value') else str(node.scope),
                    "attributes": node.attributes,
                    "created_at": getattr(node, 'created_at', None),
                    "updated_at": getattr(node, 'updated_at', None)
                },
                "relationships": [{
                    "type": rel.get('type'),
                    "direction": rel.get('direction'),
                    "target_id": rel.get('target_id'),
                    "attributes": rel.get('attributes', {})
                } for rel in relationships]
            })
        except Exception as e:
            logger.error(f"Error getting node details: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_memory_timeseries(self, request: web.Request) -> web.Response:
        """Get time-series memory data."""
        try:
            scope = request.query.get('scope', 'session')
            limit = int(request.query.get('limit', 100))
            
            memory_service = getattr(self.bus_manager, 'memory_service', None)
            if memory_service and hasattr(memory_service, 'get_timeseries'):
                results = await memory_service.get_timeseries(scope, limit)
                return web.json_response(results)
            else:
                return web.json_response({"error": "Memory timeseries not available"}, status=500)
        except Exception as e:
            logger.error(f"Error in memory timeseries: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_memory_timeline(self, request: web.Request) -> web.Response:
        """Get memory timeline - memories organized by time."""
        try:
            # Parse time parameters
            hours = int(request.query.get('hours', 24))
            scope = request.query.get('scope')
            node_type = request.query.get('type')
            
            memory_service = getattr(self.bus_manager, 'memory_service', None)
            if not memory_service:
                return web.json_response({"error": "Memory service not available"}, status=503)
            
            # Get timeline data
            timeline = []
            if hasattr(memory_service, 'get_timeline'):
                filters = {}
                if scope:
                    filters['scope'] = scope
                if node_type:
                    filters['node_type'] = node_type
                    
                timeline = await memory_service.get_timeline(hours=hours, filters=filters)
            
            # Format as time buckets
            return web.json_response({
                "timeline": timeline,
                "hours": hours,
                "filters": {
                    "scope": scope,
                    "type": node_type
                }
            })
        except Exception as e:
            logger.error(f"Error getting memory timeline: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_agent_identity(self, request: web.Request) -> web.Response:
        """Get the agent's identity from graph memory."""
        try:
            # Agent identity is always in the identity scope
            if self.bus_manager and hasattr(self.bus_manager, 'recall'):
                result = await self.bus_manager.recall(
                    node_id="AGENT_IDENTITY",
                    node_type="IDENTITY",
                    scope="identity"
                )
                
                if result and hasattr(result, 'nodes') and result.nodes:
                    identity_node = result.nodes[0]
                    return web.json_response({
                        "identity": {
                            "agent_id": identity_node.attributes.get('agent_id'),
                            "name": identity_node.attributes.get('name'),
                            "created_at": identity_node.attributes.get('created_at'),
                            "purpose": identity_node.attributes.get('purpose'),
                            "lineage": identity_node.attributes.get('lineage', {}),
                            "capabilities": identity_node.attributes.get('capabilities', []),
                            "variance_threshold": identity_node.attributes.get('variance_threshold', 0.2)
                        },
                        "node_id": identity_node.id,
                        "last_updated": getattr(identity_node, 'updated_at', None)
                    })
                else:
                    return web.json_response(
                        {"error": "Agent identity not found in graph"},
                        status=404
                    )
            else:
                return web.json_response(
                    {"error": "Memory service not available"},
                    status=503
                )
        except Exception as e:
            logger.error(f"Error getting agent identity: {e}")
            return web.json_response({"error": str(e)}, status=500)
