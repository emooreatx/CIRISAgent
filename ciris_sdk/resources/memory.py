from __future__ import annotations

from typing import Any, List, Optional, Dict, Union
from datetime import datetime

from ..transport import Transport

class MemoryResource:
    """Memory service client implementing MEMORIZE, RECALL, FORGET verbs.
    
    The memory service provides unified access to the agent's graph memory.
    All operations work through typed GraphNode objects.
    """
    
    def __init__(self, transport: Transport):
        self._transport = transport

    async def store(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Store typed nodes in memory (MEMORIZE).
        
        This is the primary way to add information to the agent's memory.
        Requires ADMIN role.
        
        Args:
            node: GraphNode data to store (as dict)
            
        Returns:
            MemoryOpResult with success status and node ID
        """
        payload = {"node": node}
        resp = await self._transport.request("POST", "/v1/memory/store", json=payload)
        return resp.json().get("data", {})

    async def query(
        self,
        *,
        node_id: Optional[str] = None,
        type: Optional[str] = None,
        query: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        related_to: Optional[str] = None,
        scope: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 20,
        offset: int = 0,
        include_edges: bool = False,
        depth: int = 1
    ) -> List[Dict[str, Any]]:
        """Flexible query interface for memory (RECALL).
        
        Supports multiple query patterns:
        - By ID: Get specific node
        - By type: Filter by node type
        - By text: Natural language search
        - By time: Temporal queries  
        - By correlation: Find related nodes
        
        Args:
            node_id: Get specific node by ID
            type: Filter by node type
            query: Text search query
            since: Memories since this time
            until: Memories until this time
            related_to: Find nodes related to this node ID
            scope: Memory scope filter
            tags: Filter by tags
            limit: Maximum results (1-100)
            offset: Pagination offset
            include_edges: Include relationship data
            depth: Graph traversal depth (1-3)
            
        Returns:
            List of GraphNode objects (as dicts)
        """
        payload = {}
        
        # Add query parameters if provided
        if node_id:
            payload["node_id"] = node_id
        if type:
            payload["type"] = type
        if query:
            payload["query"] = query
        if since:
            payload["since"] = since.isoformat() if isinstance(since, datetime) else since
        if until:
            payload["until"] = until.isoformat() if isinstance(until, datetime) else until
        if related_to:
            payload["related_to"] = related_to
        if scope:
            payload["scope"] = scope
        if tags:
            payload["tags"] = tags
            
        # Pagination and options
        payload["limit"] = limit
        payload["offset"] = offset
        payload["include_edges"] = include_edges
        payload["depth"] = depth
        
        resp = await self._transport.request("POST", "/v1/memory/query", json=payload)
        return resp.json().get("data", [])

    async def forget(self, node_id: str) -> Dict[str, Any]:
        """Remove specific memories (FORGET).
        
        Requires ADMIN role.
        
        Args:
            node_id: ID of node to forget
            
        Returns:
            MemoryOpResult with success status
        """
        resp = await self._transport.request("DELETE", f"/v1/memory/{node_id}")
        return resp.json().get("data", {})

    async def get_node(self, node_id: str) -> Dict[str, Any]:
        """Get specific node by ID.
        
        Direct access to a memory node.
        
        Args:
            node_id: Node ID to retrieve
            
        Returns:
            GraphNode object (as dict)
        """
        resp = await self._transport.request("GET", f"/v1/memory/{node_id}")
        return resp.json().get("data", {})

    async def get_timeline(
        self,
        hours: int = 24,
        bucket_size: str = "hour",
        scope: Optional[str] = None,
        type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Temporal view of memories.
        
        Get memories organized chronologically with time bucket counts.
        
        Args:
            hours: Hours to look back (1-168)
            bucket_size: Time bucket size ("hour" or "day")
            scope: Memory scope filter
            type: Node type filter
            
        Returns:
            TimelineResponse with memories and time buckets
        """
        params = {
            "hours": str(hours),
            "bucket_size": bucket_size
        }
        if scope:
            params["scope"] = scope
        if type:
            params["type"] = type
            
        resp = await self._transport.request("GET", "/v1/memory/timeline", params=params)
        return resp.json().get("data", {})

    # Deprecated methods for backwards compatibility
    async def memorize(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Deprecated: Use store() instead."""
        return await self.store(node)
    
    async def recall(
        self,
        node_id: str,
        scope: Optional[str] = None,
        node_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Deprecated: Use query() instead."""
        return await self.query(node_id=node_id, scope=scope, type=node_type)
