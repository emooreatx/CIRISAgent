"""
Memory service endpoints for CIRIS API v3 (Simplified).

The memory service implements the three universal verbs: MEMORIZE, RECALL, FORGET.
All operations work through the graph memory system.
"""
import logging
from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends, Query, Path
from pydantic import BaseModel, Field, field_serializer, model_validator

from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphScope
from ciris_engine.schemas.services.operations import MemoryQuery, MemoryOpResult
from ciris_engine.schemas.services.graph.memory import MemorySearchFilter
from ciris_engine.api.dependencies.auth import require_observer, require_admin, AuthContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])

# Request/Response schemas for simplified API

class StoreRequest(BaseModel):
    """Request to store typed nodes in memory (MEMORIZE)."""
    node: GraphNode = Field(..., description="Typed graph node to store")

class QueryRequest(BaseModel):
    """Flexible query interface for memory (RECALL).

    Supports multiple query patterns:
    - By ID: Specify node_id
    - By type: Specify type filter
    - By text: Specify query string
    - By time: Specify since/until filters
    - By correlation: Specify related_to node
    """
    # Node-based queries
    node_id: Optional[str] = Field(None, description="Get specific node by ID")
    type: Optional[NodeType] = Field(None, description="Filter by node type")

    # Text search
    query: Optional[str] = Field(None, description="Text search query")

    # Time-based queries
    since: Optional[datetime] = Field(None, description="Memories since this time")
    until: Optional[datetime] = Field(None, description="Memories until this time")

    # Correlation queries
    related_to: Optional[str] = Field(None, description="Find nodes related to this node ID")

    # Filters
    scope: Optional[GraphScope] = Field(None, description="Memory scope filter")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")

    # Pagination
    limit: int = Field(20, ge=1, le=100, description="Maximum results")
    offset: int = Field(0, ge=0, description="Pagination offset")

    # Options
    include_edges: bool = Field(False, description="Include relationship data")
    depth: int = Field(1, ge=1, le=3, description="Graph traversal depth for relationships")

    @model_validator(mode='after')
    def validate_query_params(self):
        """Ensure at least one query parameter is provided."""
        if not any([
            self.node_id,
            self.type,
            self.query,
            self.since,
            self.related_to
        ]):
            raise ValueError("At least one query parameter must be provided")
        return self

class TimelineResponse(BaseModel):
    """Temporal view of memories."""
    memories: List[GraphNode] = Field(..., description="Memories in chronological order")
    buckets: Dict[str, int] = Field(..., description="Memory counts by time bucket (hour/day)")
    start_time: datetime = Field(..., description="Start of timeline range")
    end_time: datetime = Field(..., description="End of timeline range")
    total: int = Field(..., description="Total memories in range")

    @field_serializer('start_time', 'end_time')
    def serialize_times(self, dt: datetime, _info):
        return dt.isoformat() if dt else None

# Simplified Endpoints

@router.post("/store", response_model=SuccessResponse[MemoryOpResult])
async def store_memory(
    request: Request,
    body: StoreRequest,
    auth: AuthContext = Depends(require_admin)
):
    """
    Store typed nodes in memory (MEMORIZE).

    This is the primary way to add information to the agent's memory.
    Requires ADMIN role as this modifies system state.
    """
    memory_service = getattr(request.app.state, 'memory_service', None)
    if not memory_service:
        raise HTTPException(status_code=503, detail="Memory service not available")

    try:
        result = await memory_service.memorize(body.node)
        return SuccessResponse(data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/query", response_model=SuccessResponse[List[GraphNode]])
async def query_memory(
    request: Request,
    body: QueryRequest,
    auth: AuthContext = Depends(require_observer)
):
    """
    Flexible query interface for memory (RECALL).

    This unified endpoint replaces recall/search/correlations.
    Supports multiple query patterns:
    - By ID: Get specific node
    - By type: Filter by node type
    - By text: Natural language search
    - By time: Temporal queries
    - By correlation: Find related nodes

    OBSERVER role can read all memories.
    """
    memory_service = getattr(request.app.state, 'memory_service', None)
    if not memory_service:
        raise HTTPException(status_code=503, detail="Memory service not available")

    try:
        nodes = []

        # Query by specific node ID
        if body.node_id:
            query = MemoryQuery(
                node_id=body.node_id,
                scope=body.scope or GraphScope.LOCAL,
                include_edges=body.include_edges,
                depth=body.depth
            )
            nodes = await memory_service.recall(query)

        # Text search
        elif body.query:
            filters = MemorySearchFilter(
                scope=body.scope.value if body.scope else None,
                node_type=body.type.value if body.type else None
            )
            # Note: tags filtering would need to be handled differently
            # as MemorySearchFilter doesn't have a tags field

            nodes = await memory_service.search(body.query, filters=filters)

        # Find related nodes
        elif body.related_to:
            query = MemoryQuery(
                node_id=body.related_to,
                scope=body.scope or GraphScope.LOCAL,
                include_edges=True,
                depth=body.depth or 2
            )
            related_nodes = await memory_service.recall(query)
            # Filter out the source node
            nodes = [n for n in related_nodes if n.id != body.related_to]

        # Type-based query
        elif body.type:
            # Use a broad recall with type filter
            # This is a simplified approach - in practice, the memory service
            # should support type-based queries directly
            all_nodes = await memory_service.recall(MemoryQuery(
                node_id="*",  # Wildcard to get all
                scope=body.scope or GraphScope.LOCAL,
                type=body.type,
                include_edges=False,
                depth=1
            ))
            nodes = all_nodes

        # Apply time filters if provided
        if body.since or body.until:
            filtered_nodes = []
            for node in nodes:
                node_time = node.attributes.get('created_at') or node.attributes.get('timestamp')
                if node_time:
                    if isinstance(node_time, str):
                        node_time = datetime.fromisoformat(node_time.replace('Z', '+00:00'))

                    if body.since and node_time < body.since:
                        continue
                    if body.until and node_time > body.until:
                        continue

                    filtered_nodes.append(node)
            nodes = filtered_nodes

        # Apply pagination
        _total = len(nodes)
        if body.offset:
            nodes = nodes[body.offset:]
        if body.limit:
            nodes = nodes[:body.limit]

        return SuccessResponse(data=nodes)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{node_id}", response_model=SuccessResponse[MemoryOpResult])
async def forget_memory(
    request: Request,
    node_id: str = Path(..., description="ID of node to forget"),
    auth: AuthContext = Depends(require_admin)
):
    """
    Remove specific memories (FORGET).

    Requires ADMIN role as this modifies system state.
    """
    memory_service = getattr(request.app.state, 'memory_service', None)
    if not memory_service:
        raise HTTPException(status_code=503, detail="Memory service not available")

    try:
        # First get the node
        query = MemoryQuery(
            node_id=node_id,
            scope=GraphScope.LOCAL,
            include_edges=False,
            depth=1
        )
        nodes = await memory_service.recall(query)

        if not nodes:
            raise HTTPException(
                status_code=404,
                detail=f"Node {node_id} not found"
            )

        # Forget the node
        result = await memory_service.forget(nodes[0])
        return SuccessResponse(data=result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/timeline", response_model=SuccessResponse[TimelineResponse])
async def get_timeline(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    bucket_size: str = Query("hour", description="Time bucket size: hour, day"),
    scope: Optional[GraphScope] = Query(None, description="Memory scope filter"),
    type: Optional[NodeType] = Query(None, description="Node type filter"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Temporal view of memories.

    Get memories organized chronologically with time bucket counts.
    """
    memory_service = getattr(request.app.state, 'memory_service', None)
    if not memory_service:
        raise HTTPException(status_code=503, detail="Memory service not available")

    try:
        # Calculate time range
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=hours)

        # Query memories in time range
        _query_body = QueryRequest(
            since=start_time,
            until=now,
            scope=scope,
            type=type,
            limit=100  # Maximum allowed by QueryRequest
        )

        # Reuse the query logic
        nodes = []

        # For timeline, we need a broader search
        all_query = MemoryQuery(
            node_id="*",  # Get all nodes
            scope=scope or GraphScope.LOCAL,
            type=type,
            include_edges=False,
            depth=1
        )

        try:
            all_nodes = await memory_service.recall(all_query)
        except Exception as e:
            logger.warning(f"Wildcard recall failed for query '{all_query}': {type(e).__name__}: {str(e)} - Falling back to search method")
            # Continue with fallback
            all_nodes = await memory_service.search("", filters=MemorySearchFilter(
                scope=scope,
                node_type=type
            ))

        # Filter by time
        for node in all_nodes:
            node_time = node.attributes.get('created_at') or node.attributes.get('timestamp')
            if node_time:
                if isinstance(node_time, str):
                    node_time = datetime.fromisoformat(node_time.replace('Z', '+00:00'))

                if start_time <= node_time <= now:
                    nodes.append(node)

        # Sort by time
        nodes.sort(key=lambda n: n.attributes.get('created_at') or n.attributes.get('timestamp', ''), reverse=True)

        # Create time buckets
        buckets = {}
        bucket_delta = timedelta(hours=1) if bucket_size == "hour" else timedelta(days=1)

        current_bucket = start_time
        while current_bucket < now:
            bucket_key = current_bucket.strftime("%Y-%m-%d %H:00" if bucket_size == "hour" else "%Y-%m-%d")
            buckets[bucket_key] = 0
            current_bucket += bucket_delta

        # Count nodes in buckets
        for node in nodes:
            node_time = node.attributes.get('created_at') or node.attributes.get('timestamp')
            if node_time:
                if isinstance(node_time, str):
                    node_time = datetime.fromisoformat(node_time.replace('Z', '+00:00'))

                bucket_key = node_time.strftime("%Y-%m-%d %H:00" if bucket_size == "hour" else "%Y-%m-%d")
                if bucket_key in buckets:
                    buckets[bucket_key] += 1

        response = TimelineResponse(
            memories=nodes[:100],  # Limit actual nodes returned
            buckets=buckets,
            start_time=start_time,
            end_time=now,
            total=len(nodes)
        )

        return SuccessResponse(data=response)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{node_id}", response_model=SuccessResponse[GraphNode])
async def get_memory(
    request: Request,
    node_id: str = Path(..., description="Node ID to retrieve"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get specific node by ID.

    Direct access to a memory node.
    """
    memory_service = getattr(request.app.state, 'memory_service', None)
    if not memory_service:
        raise HTTPException(status_code=503, detail="Memory service not available")

    try:
        query = MemoryQuery(
            node_id=node_id,
            scope=GraphScope.LOCAL,
            include_edges=False,
            depth=1
        )

        nodes = await memory_service.recall(query)

        if not nodes:
            raise HTTPException(
                status_code=404,
                detail=f"Node {node_id} not found"
            )

        return SuccessResponse(data=nodes[0])

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
