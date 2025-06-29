from __future__ import annotations

from typing import Any, List, Optional, Dict, Union
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from ..transport import Transport
from ..pagination import PageIterator, PaginatedResponse, QueryParams


# Request/Response Models for v1 API

class MemoryStoreRequest(BaseModel):
    """Request to store a node in memory."""
    node: Dict[str, Any] = Field(..., description="GraphNode data to store")


class MemoryStoreResponse(BaseModel):
    """Response from storing a node."""
    success: bool = Field(..., description="Whether the operation succeeded")
    node_id: str = Field(..., description="ID of the stored node")
    message: Optional[str] = Field(None, description="Status message")


class MemoryQueryRequest(BaseModel):
    """Flexible query interface for memory with top-level common filters."""
    # Common filters as top-level fields
    type: Optional[str] = Field(None, description="Filter by node type")
    tags: Optional[List[str]] = Field(None, description="Filter by tags (AND operation)")
    since: Optional[datetime] = Field(None, description="Filter by creation time (after)")
    until: Optional[datetime] = Field(None, description="Filter by creation time (before)")
    related_to: Optional[str] = Field(None, description="Find nodes related to this node ID")
    text: Optional[str] = Field(None, description="Full-text search in node content")
    
    # Advanced/custom filters
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional custom filters")
    
    # Cursor-based pagination
    cursor: Optional[str] = Field(None, description="Pagination cursor from previous response")
    limit: int = Field(20, ge=1, le=100, description="Maximum results to return")
    
    # Graph options
    include_edges: bool = Field(False, description="Include relationship data")
    depth: int = Field(1, ge=1, le=3, description="Graph traversal depth")


class GraphNode(BaseModel):
    """Basic graph node structure."""
    id: str = Field(..., description="Unique node identifier")
    type: str = Field(..., description="Node type")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Node attributes")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class MemoryQueryResponse(BaseModel):
    """Response from memory query with cursor pagination."""
    nodes: List[GraphNode] = Field(..., description="List of matching nodes")
    cursor: Optional[str] = Field(None, description="Cursor for next page of results")
    has_more: bool = Field(..., description="Whether more results are available")
    total_matches: Optional[int] = Field(None, description="Total matches (expensive, only if requested)")


class TimelineResponse(BaseModel):
    """Timeline view of memories."""
    memories: List[GraphNode] = Field(..., description="Recent memories")
    buckets: List[Dict[str, Any]] = Field(..., description="Time bucket counts")
    total: int = Field(..., description="Total memories in timeframe")


class MemoryResource:
    """
    Memory service client for v1 API (Pre-Beta).
    
    **WARNING**: This SDK is for the v1 API which is in pre-beta stage.
    The API interfaces may change without notice.
    
    The memory service provides unified access to the agent's graph memory,
    implementing MEMORIZE, RECALL, and FORGET operations through a simplified
    query interface.
    """

    def __init__(self, transport: Transport):
        self._transport = transport

    async def store(self, node: Dict[str, Any]) -> MemoryStoreResponse:
        """
        Store typed nodes in memory (MEMORIZE).

        This is the primary way to add information to the agent's memory.
        Requires: ADMIN role

        Args:
            node: GraphNode data to store (as dict)

        Returns:
            MemoryStoreResponse with success status and node ID
        
        Example:
            node = {
                "type": "CONCEPT",
                "attributes": {
                    "name": "quantum_computing",
                    "description": "A type of computation...",
                    "tags": ["physics", "computing"]
                }
            }
            result = await client.memory.store(node)
            print(f"Stored node: {result.node_id}")
        """
        payload = {"node": node}
        result = await self._transport.request("POST", "/v1/memory/store", json=payload)
        return MemoryStoreResponse(**result)

    async def query(
        self,
        *,
        type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        related_to: Optional[str] = None,
        text: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        cursor: Optional[str] = None,
        limit: int = 20,
        include_edges: bool = False,
        depth: int = 1,
        include_total: bool = False
    ) -> MemoryQueryResponse:
        """
        Flexible query interface for memory (RECALL).

        The v1 API provides top-level fields for common filters and a filters
        object for advanced/custom queries. Uses cursor-based pagination.

        Args:
            type: Filter by node type (e.g., "CONCEPT", "EXPERIENCE")
            tags: Filter by tags (AND operation)
            since: Filter by creation time (after this time)
            until: Filter by creation time (before this time)
            related_to: Find nodes related to this node ID
            text: Full-text search in node content
            filters: Additional custom filters for advanced queries
            cursor: Pagination cursor from previous response
            limit: Maximum results (1-100)
            include_edges: Include relationship data
            depth: Graph traversal depth (1-3)
            include_total: Include total match count (expensive)

        Returns:
            MemoryQueryResponse with matching nodes and optional cursor

        Examples:
            # Simple query by type
            concepts = await client.memory.query(type="CONCEPT")
            
            # Query with multiple filters
            quantum_nodes = await client.memory.query(
                type="CONCEPT",
                tags=["quantum", "physics"],
                since=datetime(2025, 1, 1)
            )
            
            # Paginated query
            first_page = await client.memory.query(type="EXPERIENCE", limit=50)
            if first_page.has_more:
                next_page = await client.memory.query(
                    type="EXPERIENCE", 
                    cursor=first_page.cursor,
                    limit=50
                )
            
            # Find related nodes with depth
            related = await client.memory.query(
                related_to="node_123",
                depth=2,
                include_edges=True
            )
        """
        payload: Dict[str, Any] = {
            "limit": limit,
            "include_edges": include_edges,
            "depth": depth
        }

        # Add top-level filters
        if type:
            payload["type"] = type
        if tags:
            payload["tags"] = tags
        if since:
            payload["since"] = since.isoformat() if isinstance(since, datetime) else since
        if until:
            payload["until"] = until.isoformat() if isinstance(until, datetime) else until
        if related_to:
            payload["related_to"] = related_to
        if text:
            payload["text"] = text
        
        # Add custom filters
        if filters:
            payload["filters"] = filters
            
        # Pagination
        if cursor:
            payload["cursor"] = cursor
            
        # Optional expensive operations
        if include_total:
            payload["include_total"] = include_total

        result = await self._transport.request("POST", "/v1/memory/query", json=payload)
        return MemoryQueryResponse(**result)
    
    def query_iter(
        self,
        *,
        type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        related_to: Optional[str] = None,
        text: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        include_edges: bool = False,
        depth: int = 1
    ) -> PageIterator[Dict[str, Any]]:
        """
        Iterate over all query results with automatic pagination.
        
        This is a convenience method that handles pagination automatically.
        It returns an async iterator that fetches new pages as needed.
        
        Args:
            Same as query() except no cursor or include_total
            
        Returns:
            Async iterator of GraphNode dictionaries
            
        Example:
            # Iterate over all concepts
            async for node in client.memory.query_iter(type="CONCEPT"):
                print(f"Found: {node['id']}")
        """
        params = {
            "type": type,
            "tags": tags,
            "since": since.isoformat() if since else None,
            "until": until.isoformat() if until else None,
            "related_to": related_to,
            "text": text,
            "filters": filters,
            "limit": limit,
            "include_edges": include_edges,
            "depth": depth
        }
        
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        
        return PageIterator(
            fetch_func=self.query,
            initial_params=params,
            item_class=dict  # Using dict since GraphNode is just a dict
        )

    async def forget(self, node_id: str) -> MemoryStoreResponse:
        """
        Remove specific memories (FORGET).

        Requires: ADMIN role

        Args:
            node_id: ID of node to forget

        Returns:
            MemoryStoreResponse with success status
        """
        result = await self._transport.request("DELETE", f"/v1/memory/{node_id}")
        return MemoryStoreResponse(**result)

    async def get_node(self, node_id: str) -> GraphNode:
        """
        Get specific node by ID.

        Direct access to a memory node.
        Requires: OBSERVER role

        Args:
            node_id: Node ID to retrieve

        Returns:
            GraphNode object
        """
        result = await self._transport.request("GET", f"/v1/memory/{node_id}")
        return GraphNode(**result)

    async def get_timeline(
        self,
        hours: int = 24,
        bucket_size: str = "hour",
        scope: Optional[str] = None,
        type: Optional[str] = None
    ) -> TimelineResponse:
        """
        Temporal view of memories.

        Get memories organized chronologically with time bucket counts.
        Requires: OBSERVER role

        Args:
            hours: Hours to look back (1-168)
            bucket_size: Time bucket size ("hour" or "day")
            scope: Memory scope filter
            type: Node type filter

        Returns:
            TimelineResponse with memories and time buckets
        
        Example:
            # Get last 24 hours of EXPERIENCE nodes
            timeline = await client.memory.get_timeline(
                hours=24,
                type="EXPERIENCE",
                bucket_size="hour"
            )
            for bucket in timeline.buckets:
                print(f"{bucket['time']}: {bucket['count']} memories")
        """
        params = {
            "hours": str(hours),
            "bucket_size": bucket_size
        }
        if scope:
            params["scope"] = scope
        if type:
            params["type"] = type

        result = await self._transport.request("GET", "/v1/memory/timeline", params=params)
        return TimelineResponse(**result)

    # Convenience methods for common queries
    
    async def query_by_type(self, node_type: str, limit: int = 20) -> List[GraphNode]:
        """
        Query nodes by type.
        
        Convenience method for type-based queries.
        
        Args:
            node_type: Type of nodes to retrieve
            limit: Maximum number of results
            
        Returns:
            List of GraphNode objects
        """
        response = await self.query(type=node_type, limit=limit)
        return response.nodes
    
    async def query_by_tags(self, tags: List[str], limit: int = 20) -> List[GraphNode]:
        """
        Query nodes by tags.
        
        Find nodes that have all specified tags.
        
        Args:
            tags: List of tags to filter by
            limit: Maximum number of results
            
        Returns:
            List of GraphNode objects
        """
        response = await self.query(tags=tags, limit=limit)
        return response.nodes
    
    async def query_recent(self, hours: int = 24, type: Optional[str] = None) -> List[GraphNode]:
        """
        Query recent nodes.
        
        Get nodes created in the last N hours.
        
        Args:
            hours: How many hours to look back
            type: Optional node type filter
            
        Returns:
            List of GraphNode objects
        """
        since = datetime.now() - timedelta(hours=hours)
        response = await self.query(
            type=type,
            since=since,
            limit=100
        )
        return response.nodes
    
    async def find_related(self, node_id: str, depth: int = 2) -> List[GraphNode]:
        """
        Find nodes related to a specific node.
        
        Args:
            node_id: ID of the source node
            depth: How many levels to traverse (1-3)
            
        Returns:
            List of related GraphNode objects
        """
        response = await self.query(
            related_to=node_id,
            depth=depth,
            include_edges=True
        )
        return response.nodes
