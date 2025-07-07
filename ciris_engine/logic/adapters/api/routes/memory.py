"""
Memory service endpoints for CIRIS API v3 (Simplified).

The memory service implements the three universal verbs: MEMORIZE, RECALL, FORGET.
All operations work through the graph memory system.
"""
import logging
from typing import List, Optional, Dict, Literal, TYPE_CHECKING, Any, Tuple
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends, Query, Path
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_serializer, model_validator

from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphScope
from ciris_engine.schemas.services.operations import MemoryQuery, MemoryOpResult
from ciris_engine.schemas.services.graph.memory import MemorySearchFilter
from ..dependencies.auth import require_observer, require_admin, AuthContext
from ciris_engine.logic.persistence.db.core import get_db_connection

if TYPE_CHECKING:
    import networkx as nx  # type: ignore[import-untyped]

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
    def validate_query_params(self) -> 'QueryRequest':
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
    def serialize_times(self, dt: datetime, _info: Any) -> Optional[str]:
        return dt.isoformat() if dt else None

class MemoryStats(BaseModel):
    """Memory graph statistics."""
    total_nodes: int = Field(0, description="Total number of nodes in memory")
    nodes_by_type: Dict[str, int] = Field(default_factory=dict, description="Node count by type")
    nodes_by_scope: Dict[str, int] = Field(default_factory=dict, description="Node count by scope")
    recent_nodes_24h: int = Field(0, description="Nodes created/updated in last 24 hours")
    oldest_node_date: Optional[datetime] = Field(None, description="Timestamp of oldest node")
    newest_node_date: Optional[datetime] = Field(None, description="Timestamp of newest node")
    
    @field_serializer('oldest_node_date', 'newest_node_date')
    def serialize_dates(self, dt: datetime, _info: Any) -> Optional[str]:
        return dt.isoformat() if dt else None

# Simplified Endpoints

@router.post("/store", response_model=SuccessResponse[MemoryOpResult])
async def store_memory(
    request: Request,
    body: StoreRequest,
    auth: AuthContext = Depends(require_admin)
) -> SuccessResponse[MemoryOpResult]:
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
) -> SuccessResponse[List[GraphNode]]:
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
                type=body.type,
                include_edges=body.include_edges,
                depth=body.depth
            )
            nodes = await memory_service.recall(query)

        # Text search
        elif body.query:
            filters = MemorySearchFilter(
                scope=body.scope.value if body.scope else None,
                node_type=body.type.value if body.type else None,
                created_after=body.since,
                created_before=body.until,
                created_by=None,
                has_attributes=None,
                attribute_values=None,
                limit=body.limit,
                offset=body.offset
            )
            # Note: tags filtering would need to be handled differently
            # as MemorySearchFilter doesn't have a tags field

            nodes = await memory_service.search(body.query, filters=filters)

        # Find related nodes
        elif body.related_to:
            query = MemoryQuery(
                node_id=body.related_to,
                scope=body.scope or GraphScope.LOCAL,
                type=body.type,
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
                if isinstance(node.attributes, dict):
                    node_time = node.attributes.get('created_at') or node.attributes.get('timestamp')
                else:
                    node_time = node.attributes.created_at
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
) -> SuccessResponse[MemoryOpResult]:
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
            type=None,
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
    limit: Optional[int] = Query(100, ge=1, le=1000, description="Maximum number of memories to return"),
    auth: AuthContext = Depends(require_observer)
) -> SuccessResponse[TimelineResponse]:
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
        # Note: This is just for validation/documentation purposes, not actually used
        _query_body = QueryRequest(
            node_id=None,
            query=None,
            related_to=None,
            since=start_time,
            until=now,
            scope=scope,
            type=type,
            tags=None,
            limit=limit or 100,  # Use the provided limit parameter with default
            offset=0,
            include_edges=False,
            depth=1
        )

        # For timeline, we need to query nodes within the time range directly
        # The standard recall/search methods order by updated_at DESC which gives us only recent nodes
        nodes = []
        
        # Import database utilities
        from ciris_engine.logic.persistence import get_db_connection
        from ciris_engine.schemas.services.graph_core import GraphNode, NodeType as NodeTypeEnum
        import json
        
        # Query the database directly for timeline data
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # For timeline, we need to sample across time buckets
                # First, get the days in our range
                days_in_range = int((now - start_time).total_seconds() / 86400) + 1
                nodes_per_day = max(1, (limit or 100) // days_in_range)
                
                # Sample nodes from each day
                all_db_nodes = []
                for day_offset in range(days_in_range):
                    day_start = (now - timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
                    day_end = day_start + timedelta(days=1)
                    
                    # Build query for this day
                    query_parts = [
                        "SELECT node_id, scope, node_type, attributes_json, version, updated_by, updated_at, created_at",
                        "FROM graph_nodes",
                        "WHERE updated_at >= ? AND updated_at < ?",
                        "AND NOT (node_type = 'tsdb_data' AND node_id LIKE 'metric_%')"
                    ]
                    params = [day_start.isoformat(), day_end.isoformat()]
                    
                    # Add scope filter
                    if scope:
                        query_parts.append("AND scope = ?")
                        params.append(scope.value)
                    
                    # Add type filter
                    if type:
                        query_parts.append("AND node_type = ?")
                        params.append(type.value)
                    
                    # Random sampling for better distribution
                    query_parts.extend([
                        "ORDER BY RANDOM()",
                        "LIMIT ?"
                    ])
                    params.append(nodes_per_day * 2)  # Get extra to allow for filtering
                
                    query = " ".join(query_parts)
                    cursor.execute(query, params)
                    
                    # Convert rows to GraphNode objects for this day
                    for row in cursor.fetchall():
                        try:
                            # Parse attributes
                            attributes = json.loads(row['attributes_json']) if row['attributes_json'] else {}
                            
                            # Create GraphNode
                            node = GraphNode(
                                id=row['node_id'],
                                type=NodeTypeEnum(row['node_type']),
                                scope=GraphScope(row['scope']),
                                attributes=attributes,
                                version=row['version'],
                                updated_by=row['updated_by'],
                                updated_at=datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00'))
                            )
                            all_db_nodes.append(node)
                        except Exception as e:
                            logger.warning(f"Failed to parse node {row['node_id']}: {e}")
                            continue
                
                # For timeline layout, sample nodes evenly across time range
                if len(all_db_nodes) > (limit or 100):
                    # Group by hour buckets
                    hour_buckets = {}
                    for node in all_db_nodes:
                        hour = node.updated_at.replace(minute=0, second=0, microsecond=0)
                        if hour not in hour_buckets:
                            hour_buckets[hour] = []
                        hour_buckets[hour].append(node)
                    
                    # Sample nodes from each bucket
                    target_per_bucket = max(1, (limit or 100) // len(hour_buckets)) if hour_buckets else 1
                    for hour, bucket_nodes in hour_buckets.items():
                        # Take up to target_per_bucket nodes from each hour
                        sampled = bucket_nodes[:target_per_bucket]
                        nodes.extend(sampled)
                    
                    # If we don't have enough, add more from the most populated buckets
                    if len(nodes) < (limit or 100):
                        remaining = (limit or 100) - len(nodes)
                        sorted_buckets = sorted(hour_buckets.items(), key=lambda x: len(x[1]), reverse=True)
                        for hour, bucket_nodes in sorted_buckets:
                            already_taken = min(target_per_bucket, len(bucket_nodes))
                            available = bucket_nodes[already_taken:]
                            if available:
                                take = min(len(available), remaining)
                                nodes.extend(available[:take])
                                remaining -= take
                                if remaining <= 0:
                                    break
                else:
                    nodes = all_db_nodes
                        
        except Exception as e:
            logger.error(f"Failed to query timeline data: {e}")
            # Fall back to standard search
            all_nodes = await memory_service.search("", filters=MemorySearchFilter(
                scope=scope.value if scope else None,
                node_type=type.value if type else None,
                limit=1000
            ))
            
            # Filter by time
            for node in all_nodes:
                if isinstance(node.attributes, dict):
                    node_time = node.attributes.get('created_at') or node.attributes.get('timestamp')
                else:
                    node_time = node.attributes.created_at
                
                # Fallback to top-level updated_at
                if not node_time and hasattr(node, 'updated_at'):
                    node_time = node.updated_at
                
                if node_time:
                    if isinstance(node_time, str):
                        node_time = datetime.fromisoformat(node_time.replace('Z', '+00:00'))

                    if start_time <= node_time <= now:
                        nodes.append(node)

        # Sort by time
        def get_node_time(n: GraphNode) -> str:
            if isinstance(n.attributes, dict):
                time_val = n.attributes.get('created_at') or n.attributes.get('timestamp', '')
            else:
                time_val = n.attributes.created_at or ''
            
            # Fallback to top-level updated_at
            if not time_val and hasattr(n, 'updated_at'):
                time_val = n.updated_at
            
            return str(time_val) if time_val else ''
        nodes.sort(key=get_node_time, reverse=True)

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
            if isinstance(node.attributes, dict):
                node_time = node.attributes.get('created_at') or node.attributes.get('timestamp')
            else:
                node_time = node.attributes.created_at
            
            # Fallback to top-level updated_at
            if not node_time and hasattr(node, 'updated_at'):
                node_time = node.updated_at
            
            if node_time:
                if isinstance(node_time, str):
                    node_time = datetime.fromisoformat(node_time.replace('Z', '+00:00'))

                bucket_key = node_time.strftime("%Y-%m-%d %H:00" if bucket_size == "hour" else "%Y-%m-%d")
                if bucket_key in buckets:
                    buckets[bucket_key] += 1

        response = TimelineResponse(
            memories=nodes[:limit],  # Limit actual nodes returned
            buckets=buckets,
            start_time=start_time,
            end_time=now,
            total=len(nodes)
        )

        return SuccessResponse(data=response)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recall/{node_id}", response_model=SuccessResponse[GraphNode])
async def recall_memory(
    request: Request,
    node_id: str = Path(..., description="Node ID to recall"),
    auth: AuthContext = Depends(require_observer)
) -> SuccessResponse[GraphNode]:
    """
    Recall specific memory by ID.

    Direct access to a memory node using the RECALL verb.
    """
    return await get_memory(request, node_id, auth)

@router.get("/{node_id}", response_model=SuccessResponse[GraphNode])
async def get_memory(
    request: Request,
    node_id: str = Path(..., description="Node ID to retrieve"),
    auth: AuthContext = Depends(require_observer)
) -> SuccessResponse[GraphNode]:
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
            type=None,
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

@router.get("/visualize/graph")
async def visualize_memory_graph(
    request: Request,
    node_type: Optional[NodeType] = Query(None, description="Filter by node type"),
    scope: Optional[GraphScope] = Query(GraphScope.LOCAL, description="Memory scope"),
    hours: Optional[int] = Query(None, ge=1, le=168, description="Hours to look back for timeline view"),
    layout: Literal["force", "timeline", "hierarchical"] = Query("force", description="Graph layout algorithm"),
    width: int = Query(1200, ge=400, le=4000, description="SVG width in pixels"),
    height: int = Query(800, ge=300, le=3000, description="SVG height in pixels"),
    limit: int = Query(50, ge=1, le=200, description="Maximum nodes to visualize"),
    include_metrics: bool = Query(False, description="Include metric TSDB_DATA nodes"),
    auth: AuthContext = Depends(require_observer)
) -> Response:
    """
    Generate an SVG visualization of the memory graph.
    
    Layout options:
    - force: Force-directed layout for general graph visualization
    - timeline: Arrange nodes chronologically along x-axis
    - hierarchical: Tree-like layout based on relationships
    
    Returns SVG image that can be embedded or downloaded.
    """
    memory_service = getattr(request.app.state, 'memory_service', None)
    if not memory_service:
        raise HTTPException(status_code=503, detail="Memory service not available")
    
    try:
        # Import visualization dependencies
        import networkx as nx
        from datetime import datetime
        
        # Query nodes based on filters
        nodes = []
        
        if hours:
            # Timeline view - get nodes from the specified time range
            now = datetime.now(timezone.utc)
            since = now - timedelta(hours=hours)
            
            # For timeline layout, query database directly to get time-distributed nodes
            if layout == "timeline":
                import json
                
                try:
                    logger.info(f"Timeline visualization: Querying database for {hours} hours with limit {limit}")
                    with get_db_connection() as conn:
                        cursor = conn.cursor()
                        
                        # For timeline, we need to sample across time buckets
                        days_in_range = int((now - since).total_seconds() / 86400) + 1
                        nodes_per_day = max(1, limit // days_in_range)
                        logger.info(f"Timeline: {days_in_range} days, {nodes_per_day} nodes per day")
                        
                        # Sample nodes from each day
                        all_db_nodes = []
                        for day_offset in range(days_in_range):
                            day_start = (now - timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
                            day_end = day_start + timedelta(days=1)
                            
                            # Build query for this day
                            query_parts = [
                                "SELECT node_id, scope, node_type, attributes_json, version, updated_by, updated_at, created_at",
                                "FROM graph_nodes",
                                "WHERE updated_at >= ? AND updated_at < ?",
                            ]
                            params = [day_start.isoformat(), day_end.isoformat()]
                            
                            # Add metric filter
                            if not include_metrics:
                                query_parts.append("AND NOT (node_type = 'tsdb_data' AND node_id LIKE 'metric_%')")
                            
                            # Add scope filter
                            if scope:
                                query_parts.append("AND scope = ?")
                                params.append(scope.value)
                            
                            # Add type filter
                            if node_type:
                                query_parts.append("AND node_type = ?")
                                params.append(node_type.value)
                            
                            # Random sampling for better distribution
                            query_parts.extend([
                                "ORDER BY RANDOM()",
                                "LIMIT ?"
                            ])
                            params.append(nodes_per_day * 2)  # Get extra to allow for filtering
                        
                            query = " ".join(query_parts)
                            cursor.execute(query, params)
                            
                            # Convert rows to GraphNode objects for this day
                            for row in cursor.fetchall():
                                try:
                                    # Parse attributes
                                    attributes = json.loads(row['attributes_json']) if row['attributes_json'] else {}
                                    
                                    # Create GraphNode
                                    node = GraphNode(
                                        id=row['node_id'],
                                        type=NodeType(row['node_type']),
                                        scope=GraphScope(row['scope']),
                                        attributes=attributes,
                                        version=row['version'],
                                        updated_by=row['updated_by'],
                                        updated_at=datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00'))
                                    )
                                    all_db_nodes.append(node)
                                except Exception as e:
                                    logger.warning(f"Failed to parse node {row['node_id']}: {e}")
                                    continue
                        
                        # Set nodes from database query
                        nodes = all_db_nodes[:limit] if len(all_db_nodes) > limit else all_db_nodes
                        logger.info(f"Timeline: Collected {len(all_db_nodes)} nodes, using {len(nodes)} for visualization")
                        
                except Exception as e:
                    logger.error(f"Failed to query timeline data: {e}")
                    # Fall back to standard query
                    query = MemoryQuery(
                        node_id="*",
                        scope=scope or GraphScope.LOCAL,
                        type=node_type,
                        include_edges=False,
                        depth=1
                    )
                    all_nodes = await memory_service.recall(query)
                    nodes = all_nodes
            else:
                # Regular time-based query
                query = MemoryQuery(
                    node_id="*",
                    scope=scope or GraphScope.LOCAL,
                    type=node_type,
                    include_edges=False,
                    depth=1
                )
                all_nodes = await memory_service.recall(query)
            
            # Skip additional filtering if we already have nodes from timeline database query
            if layout != "timeline" and nodes == []:
                # Filter out metric_ TSDB_DATA nodes by default unless specifically requested
                if not include_metrics and node_type != NodeType.TSDB_DATA:
                    all_nodes = [n for n in all_nodes if not (n.type == NodeType.TSDB_DATA and n.id.startswith('metric_'))]
                
                # Filter by time
                for node in all_nodes:
                    if isinstance(node.attributes, dict):
                        node_time = node.attributes.get('created_at') or node.attributes.get('timestamp')
                    else:
                        node_time = node.attributes.created_at
                    
                    # Fallback to top-level updated_at
                    if not node_time and hasattr(node, 'updated_at'):
                        node_time = node.updated_at
                    
                    if node_time:
                        if isinstance(node_time, str):
                            node_time = datetime.fromisoformat(node_time.replace('Z', '+00:00'))
                        
                        # Ensure node_time has timezone info for comparison
                        if isinstance(node_time, datetime):
                            if node_time.tzinfo is None:
                                # Assume UTC if no timezone
                                node_time = node_time.replace(tzinfo=timezone.utc)
                            
                            if since <= node_time <= now:
                                nodes.append(node)
            
            # Sort by time for timeline layout
            def get_node_sort_time(n: GraphNode) -> datetime:
                """Get datetime for sorting, with fallback to epoch."""
                epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
                try:
                    if isinstance(n.attributes, dict):
                        time_val = n.attributes.get('created_at') or n.attributes.get('timestamp')
                    else:
                        time_val = n.attributes.created_at
                    
                    # Fallback to top-level updated_at
                    if not time_val and hasattr(n, 'updated_at'):
                        time_val = n.updated_at
                    
                    if time_val:
                        if isinstance(time_val, str):
                            return datetime.fromisoformat(time_val.replace('Z', '+00:00'))
                        elif isinstance(time_val, datetime):
                            return time_val
                except Exception as e:
                    logger.warning(f"Failed to parse time for node {n.id}: {e}")
                
                return epoch
            if nodes:  # Only sort if we have nodes from time filtering
                nodes.sort(key=get_node_sort_time)
        else:
            # Regular query - get nodes with optional type filter
            # For timeline layout, we need many more nodes to cover time range
            if layout == "timeline":
                # Query database directly for timeline to get proper time distribution
                import json
                
                now = datetime.now(timezone.utc)
                start_time = now - timedelta(hours=hours)
                
                try:
                    logger.info(f"Timeline visualization: Querying database for {hours} hours with limit {limit}")
                    with get_db_connection() as conn:
                        cursor = conn.cursor()
                        
                        # For timeline, we need to sample across time buckets
                        days_in_range = int((now - start_time).total_seconds() / 86400) + 1
                        nodes_per_day = max(1, limit // days_in_range)
                        logger.info(f"Timeline: {days_in_range} days, {nodes_per_day} nodes per day")
                        
                        # Sample nodes from each day
                        all_db_nodes = []
                        for day_offset in range(days_in_range):
                            day_start = (now - timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
                            day_end = day_start + timedelta(days=1)
                            
                            # Build query for this day
                            query_parts = [
                                "SELECT node_id, scope, node_type, attributes_json, version, updated_by, updated_at, created_at",
                                "FROM graph_nodes",
                                "WHERE updated_at >= ? AND updated_at < ?",
                            ]
                            params = [day_start.isoformat(), day_end.isoformat()]
                            
                            # Add metric filter
                            if not include_metrics:
                                query_parts.append("AND NOT (node_type = 'tsdb_data' AND node_id LIKE 'metric_%')")
                            
                            # Add scope filter
                            if scope:
                                query_parts.append("AND scope = ?")
                                params.append(scope.value)
                            
                            # Add type filter
                            if node_type:
                                query_parts.append("AND node_type = ?")
                                params.append(node_type.value)
                            
                            # Random sampling for better distribution
                            query_parts.extend([
                                "ORDER BY RANDOM()",
                                "LIMIT ?"
                            ])
                            params.append(nodes_per_day * 2)  # Get extra to allow for filtering
                        
                            query = " ".join(query_parts)
                            cursor.execute(query, params)
                            
                            # Convert rows to GraphNode objects for this day
                            for row in cursor.fetchall():
                                try:
                                    # Parse attributes
                                    attributes = json.loads(row['attributes_json']) if row['attributes_json'] else {}
                                    
                                    # Create GraphNode
                                    node = GraphNode(
                                        id=row['node_id'],
                                        type=NodeType(row['node_type']),
                                        scope=GraphScope(row['scope']),
                                        attributes=attributes,
                                        version=row['version'],
                                        updated_by=row['updated_by'],
                                        updated_at=datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00'))
                                    )
                                    all_db_nodes.append(node)
                                except Exception as e:
                                    logger.warning(f"Failed to parse node {row['node_id']}: {e}")
                                    continue
                        
                        # Limit nodes if we got too many
                        logger.info(f"Timeline: Collected {len(all_db_nodes)} total nodes from database")
                        if len(all_db_nodes) > limit:
                            # Sample evenly across the collected nodes
                            step = len(all_db_nodes) // limit
                            nodes = [all_db_nodes[i] for i in range(0, len(all_db_nodes), step)][:limit]
                        else:
                            nodes = all_db_nodes
                        logger.info(f"Timeline: Using {len(nodes)} nodes for visualization")
                            
                except Exception as e:
                    logger.error(f"Failed to query timeline data: {e}")
                    # Fall back to standard search
                    search_filters = MemorySearchFilter(
                        scope=(scope or GraphScope.LOCAL).value,
                        node_type=node_type.value if node_type else None,
                        limit=limit,
                        offset=None
                    )
                    nodes = await memory_service.search("", filters=search_filters)
            else:
                # Regular query for non-timeline layouts
                query = MemoryQuery(
                    node_id="*",
                    scope=scope or GraphScope.LOCAL,
                    type=node_type,
                    include_edges=False,
                    depth=1
                )
                nodes = await memory_service.recall(query)
                
                # Filter out TSDB_DATA nodes by default unless specifically requested
                if node_type != NodeType.TSDB_DATA:
                    nodes = [n for n in nodes if n.type != NodeType.TSDB_DATA]
                
                # Apply limit for non-timeline layouts
                nodes = nodes[:limit]
        
        # Don't limit here - we handle limiting differently for timeline layout
        
        # Debug log sample node data
        if nodes and layout == "timeline":
            logger.info(f"Visualizing {len(nodes)} nodes in timeline layout")
            for i, node in enumerate(nodes[:3]):  # Log first 3 nodes
                logger.info(f"Sample node {i}: id={node.id}, type={node.type}")
                if hasattr(node, 'updated_at'):
                    logger.info(f"  updated_at: {node.updated_at}")
                if hasattr(node, 'attributes'):
                    if isinstance(node.attributes, dict):
                        logger.info(f"  attributes keys: {list(node.attributes.keys())}")
                        if 'created_at' in node.attributes:
                            logger.info(f"  created_at: {node.attributes['created_at']}")
                        if 'timestamp' in node.attributes:
                            logger.info(f"  timestamp: {node.attributes['timestamp']}")
                    else:
                        logger.info(f"  attributes type: {type(node.attributes)}")
        
        if not nodes:
            # Return empty SVG if no nodes
            svg = f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
                <rect width="{width}" height="{height}" fill="#f8f9fa"/>
                <text x="{width//2}" y="{height//2}" text-anchor="middle" font-family="Arial" font-size="16" fill="#6c757d">
                    No memories found
                </text>
            </svg>'''
            return Response(content=svg, media_type="image/svg+xml")
        
        # Create graph
        G = nx.DiGraph()
        
        # Add nodes with their attributes
        for node in nodes:
            # Prepare node attributes for visualization
            node_attrs = {
                'label': node.id[:30] + '...' if len(node.id) > 30 else node.id,
                'type': node.type.value,
                'scope': node.scope.value,
                'title': node.attributes.get('title', '') if isinstance(node.attributes, dict) else '',
                'created_at': (node.attributes.get('created_at') or node.attributes.get('timestamp') or str(getattr(node, 'updated_at', ''))) if isinstance(node.attributes, dict) else str(getattr(node.attributes, 'created_at', getattr(node, 'updated_at', ''))),
                'color': _get_node_color(node.type),
                'size': _get_node_size(node)
            }
            G.add_node(node.id, **node_attrs)
        
        # TODO: Add edges if we implement relationship queries
        
        # Calculate layout based on selected algorithm
        if layout == "timeline" and hours:
            pos = _calculate_timeline_layout(G, nodes, width, height)
        elif layout == "hierarchical":
            pos = nx.spring_layout(G, k=2, iterations=50)
            # Scale to fit canvas
            pos = {node: (x * (width - 100) + 50, y * (height - 100) + 50) for node, (x, y) in pos.items()}
        else:  # force layout
            pos = nx.spring_layout(G, k=1.5, iterations=30)
            # Scale to fit canvas
            pos = {node: (x * (width - 100) + 50, y * (height - 100) + 50) for node, (x, y) in pos.items()}
        
        # Generate SVG
        svg = _generate_svg(G, pos, width, height, layout, hours)
        
        return Response(content=svg, media_type="image/svg+xml")
        
    except ImportError:
        raise HTTPException(
            status_code=503, 
            detail="Graph visualization requires networkx. Please install: pip install networkx"
        )
    except Exception as e:
        logger.exception(f"Error generating graph visualization: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _get_node_color(node_type: NodeType) -> str:
    """Get color for node based on type."""
    color_map = {
        NodeType.AGENT: "#4CAF50",      # Green
        NodeType.USER: "#2196F3",       # Blue
        NodeType.CHANNEL: "#9C27B0",    # Purple
        NodeType.CONCEPT: "#FF9800",    # Orange
        NodeType.CONFIG: "#795548",     # Brown
        NodeType.TSDB_DATA: "#00BCD4",  # Cyan
        NodeType.OBSERVATION: "#E91E63", # Pink
        NodeType.IDENTITY: "#3F51B5",   # Indigo
        NodeType.AUDIT_ENTRY: "#607D8B", # Blue Grey
    }
    return color_map.get(node_type, "#9E9E9E")  # Default grey


def _get_node_size(node: GraphNode) -> int:
    """Calculate node size based on importance/attributes."""
    base_size = 30
    
    # Increase size for nodes with more attributes
    if node.attributes:
        if isinstance(node.attributes, dict):
            attr_count = len([k for k, v in node.attributes.items() if v is not None])
        else:
            # Count non-None fields in GraphNodeAttributes
            attr_count = len([f for f in node.attributes.model_fields if getattr(node.attributes, f, None) is not None])
        base_size += min(attr_count * 2, 20)
    
    # Increase size for identity-related nodes
    if node.scope == GraphScope.IDENTITY:
        base_size += 10
    
    return base_size


def _calculate_timeline_layout(G: "nx.DiGraph", nodes: List[GraphNode], width: int, height: int) -> Dict[str, Tuple[float, float]]:
    """Calculate timeline layout with nodes arranged chronologically."""
    pos = {}
    
    # Group nodes by time buckets (hourly)
    time_buckets: Dict[datetime, List[str]] = {}
    nodes_without_time = []
    
    for node in nodes:
        node_time = None
        try:
            # Try to get timestamp from various sources
            if isinstance(node.attributes, dict):
                node_time = node.attributes.get('created_at') or node.attributes.get('timestamp')
            else:
                node_time = node.attributes.created_at
            
            # Fallback to top-level updated_at if no timestamp in attributes
            if not node_time and hasattr(node, 'updated_at'):
                node_time = node.updated_at
            
            if node_time:
                # Debug log the raw timestamp value
                logger.debug(f"Node {node.id} raw timestamp: {node_time} (type: {type(node_time)})")
                
                # Convert string to datetime if needed
                if isinstance(node_time, str):
                    # Handle ISO format with Z suffix
                    node_time = datetime.fromisoformat(node_time.replace('Z', '+00:00'))
                
                # Ensure we have a datetime object before rounding
                if isinstance(node_time, datetime):
                    # Ensure timezone info
                    if node_time.tzinfo is None:
                        node_time = node_time.replace(tzinfo=timezone.utc)
                    
                    # Round to hour
                    bucket = node_time.replace(minute=0, second=0, microsecond=0)
                    if bucket not in time_buckets:
                        time_buckets[bucket] = []
                    time_buckets[bucket].append(node.id)
                    logger.debug(f"Node {node.id} bucketed to: {bucket.isoformat()}")
                else:
                    logger.warning(f"Node {node.id} has non-datetime timestamp after parsing: {node_time}")
                    nodes_without_time.append(node.id)
            else:
                nodes_without_time.append(node.id)
        except Exception as e:
            logger.warning(f"Failed to parse timestamp for node {node.id}: {e}")
            nodes_without_time.append(node.id)
    
    # Sort buckets by time
    sorted_buckets = sorted(time_buckets.items())
    
    # Enhanced debug logging for timeline bucketing
    if sorted_buckets:
        logger.info(f"Timeline layout: {len(sorted_buckets)} time buckets found")
        logger.info(f"First bucket: {sorted_buckets[0][0].isoformat()} with {len(sorted_buckets[0][1])} nodes")
        logger.info(f"Last bucket: {sorted_buckets[-1][0].isoformat()} with {len(sorted_buckets[-1][1])} nodes")
        logger.info(f"Total nodes in timeline: {sum(len(nodes) for _, nodes in sorted_buckets)}")
        
        # Log all buckets for debugging
        for i, (bucket_time, bucket_nodes) in enumerate(sorted_buckets[:5]):  # First 5 buckets
            logger.info(f"Bucket {i}: {bucket_time.isoformat()} has {len(bucket_nodes)} nodes")
    
    if nodes_without_time:
        logger.info(f"Nodes without timestamps: {len(nodes_without_time)} nodes")
    
    if not sorted_buckets:
        # Fallback to force layout if no timestamps
        layout_result = nx.spring_layout(G)
        # Convert to proper type
        return {node: (float(x), float(y)) for node, (x, y) in layout_result.items()}
    
    # Calculate x positions for each time bucket
    x_spacing = (width - 100) / max(len(sorted_buckets) - 1, 1)
    
    logger.info(f"Timeline layout calculation: width={width}, buckets={len(sorted_buckets)}, x_spacing={x_spacing}")
    
    for i, (bucket_time, node_ids) in enumerate(sorted_buckets):
        x = 50 + i * x_spacing
        
        # Log position calculation for first few buckets
        if i < 3:
            logger.info(f"Bucket {i} at {bucket_time.isoformat()}: x={x}, nodes={len(node_ids)}")
        
        # Distribute nodes vertically within each time bucket
        y_spacing = (height - 100) / max(len(node_ids), 1)
        for j, node_id in enumerate(node_ids):
            y = 50 + j * y_spacing + (y_spacing / 2)
            pos[node_id] = (x, y)
    
    # Log final position summary
    if pos:
        x_positions = sorted(set(x for x, y in pos.values()))
        logger.info(f"Timeline positions assigned: {len(pos)} nodes across {len(x_positions)} unique x-positions")
        logger.info(f"X-position range: {min(x_positions):.1f} to {max(x_positions):.1f}")
        if len(x_positions) <= 5:
            logger.info(f"All x-positions: {[f'{x:.1f}' for x in x_positions]}")
    
    return pos


def _generate_svg(G: "nx.DiGraph", pos: Dict[str, tuple], width: int, height: int, 
                  layout: str, hours: Optional[int]) -> str:
    """Generate SVG visualization of the graph."""
    svg_parts = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect width="{width}" height="{height}" fill="#f8f9fa"/>',
        '<defs>',
        '<marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">',
        '<polygon points="0 0, 10 3.5, 0 7" fill="#999" />',
        '</marker>',
        '</defs>'
    ]
    
    # Add title
    title = f"Memory Graph Visualization"
    if layout == "timeline" and hours:
        title = f"Memory Timeline - Last {hours} hours"
    svg_parts.append(
        f'<text x="{width//2}" y="30" text-anchor="middle" font-family="Arial" '
        f'font-size="20" font-weight="bold" fill="#333">{title}</text>'
    )
    
    # Draw edges (if any)
    for edge in G.edges():
        x1, y1 = pos[edge[0]]
        x2, y2 = pos[edge[1]]
        svg_parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="#999" stroke-width="2" marker-end="url(#arrowhead)" opacity="0.6"/>'
        )
    
    # Draw nodes
    for node_id, attrs in G.nodes(data=True):
        x, y = pos[node_id]
        color = attrs.get('color', '#9E9E9E')
        size = attrs.get('size', 30)
        label = attrs.get('label', node_id)
        node_type = attrs.get('type', 'unknown')
        
        # Node circle with data-node-id attribute for click handling
        svg_parts.append(
            f'<circle cx="{x}" cy="{y}" r="{size}" fill="{color}" '
            f'stroke="#333" stroke-width="2" opacity="0.8" '
            f'data-node-id="{node_id}"/>'
        )
        
        # Node label
        svg_parts.append(
            f'<text x="{x}" y="{y + size + 15}" text-anchor="middle" '
            f'font-family="Arial" font-size="12" fill="#333">{label}</text>'
        )
        
        # Node type label
        svg_parts.append(
            f'<text x="{x}" y="{y + 5}" text-anchor="middle" '
            f'font-family="Arial" font-size="10" fill="white" font-weight="bold">{node_type}</text>'
        )
    
    # Add timeline axis if in timeline mode
    if layout == "timeline" and hours:
        # Draw time axis
        svg_parts.append(
            f'<line x1="50" y1="{height - 40}" x2="{width - 50}" y2="{height - 40}" '
            f'stroke="#666" stroke-width="2"/>'
        )
        
        # Add time labels with fixed intervals
        now = datetime.now(timezone.utc)
        # Use predefined safe intervals based on hours range
        if hours <= 6:
            intervals = [0, 1, 2, 3, 4, 5, hours][:hours+1]
        elif hours <= 24:
            intervals = [0, 4, 8, 12, 16, 20, hours]
        elif hours <= 48:
            intervals = [0, 8, 16, 24, 32, 40, hours]
        elif hours <= 96:
            intervals = [0, 16, 32, 48, 64, 80, hours]
        else:  # hours <= 168
            intervals = [0, 24, 48, 72, 96, 120, 144, hours]
        
        # Filter out any duplicates and sort
        intervals = sorted(set(i for i in intervals if i <= hours))
        
        for hour in intervals:
            x = 50 + (hour / hours) * (width - 100)
            time_label = (now - timedelta(hours=hours-hour)).strftime("%m/%d %H:%M")
            svg_parts.append(
                f'<text x="{x}" y="{height - 20}" text-anchor="middle" '
                f'font-family="Arial" font-size="10" fill="#666">{time_label}</text>'
            )
    
    # Add legend
    legend_y = height - 150
    svg_parts.append(
        f'<text x="20" y="{legend_y}" font-family="Arial" font-size="14" '
        f'font-weight="bold" fill="#333">Node Types:</text>'
    )
    
    type_colors = [
        (NodeType.CONCEPT, "Concept"),
        (NodeType.OBSERVATION, "Observation"),
        (NodeType.IDENTITY, "Identity"),
        (NodeType.CONFIG, "Config"),
    ]
    
    for i, (node_type, label) in enumerate(type_colors):
        y_offset = legend_y + 20 + i * 20
        color = _get_node_color(node_type)
        svg_parts.append(
            f'<circle cx="30" cy="{y_offset}" r="8" fill="{color}" stroke="#333" stroke-width="1"/>'
        )
        svg_parts.append(
            f'<text x="45" y="{y_offset + 5}" font-family="Arial" font-size="12" fill="#333">{label}</text>'
        )
    
    svg_parts.append('</svg>')
    
    return '\n'.join(svg_parts)


@router.get("/stats", response_model=SuccessResponse[MemoryStats])
async def get_memory_stats(
    request: Request,
    auth: AuthContext = Depends(require_observer)
) -> SuccessResponse[MemoryStats]:
    """
    Get memory graph statistics.
    
    Returns counts and metadata about nodes in memory without requiring any query parameters.
    OBSERVER role can view memory statistics.
    """
    try:
        stats = MemoryStats()
        
        # Get stats from database
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Total node count
            cursor.execute("SELECT COUNT(*) as total FROM graph_nodes")
            stats.total_nodes = cursor.fetchone()['total'] or 0
            
            # Nodes by type
            cursor.execute("""
                SELECT node_type, COUNT(*) as count 
                FROM graph_nodes 
                GROUP BY node_type
            """)
            stats.nodes_by_type = {row['node_type']: row['count'] for row in cursor.fetchall()}
            
            # Nodes by scope  
            cursor.execute("""
                SELECT scope, COUNT(*) as count 
                FROM graph_nodes 
                GROUP BY scope
            """)
            stats.nodes_by_scope = {row['scope']: row['count'] for row in cursor.fetchall()}
            
            # Recent nodes (24h)
            twenty_four_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM graph_nodes 
                WHERE updated_at >= ?
            """, (twenty_four_hours_ago,))
            stats.recent_nodes_24h = cursor.fetchone()['count'] or 0
            
            # Date range
            cursor.execute("""
                SELECT 
                    MIN(updated_at) as oldest,
                    MAX(updated_at) as newest
                FROM graph_nodes
            """)
            row = cursor.fetchone()
            if row and row['oldest']:
                stats.oldest_node_date = datetime.fromisoformat(row['oldest'].replace('Z', '+00:00'))
            if row and row['newest']:
                stats.newest_node_date = datetime.fromisoformat(row['newest'].replace('Z', '+00:00'))
        
        return SuccessResponse(data=stats)
        
    except Exception as e:
        logger.error(f"Failed to get memory stats: {e}")
        # Return empty stats on error
        return SuccessResponse(data=MemoryStats())
