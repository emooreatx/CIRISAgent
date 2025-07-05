"""
Memory service endpoints for CIRIS API v3 (Simplified).

The memory service implements the three universal verbs: MEMORIZE, RECALL, FORGET.
All operations work through the graph memory system.
"""
import logging
from typing import List, Optional, Dict, Literal, TYPE_CHECKING
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends, Query, Path
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_serializer, model_validator

from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphScope
from ciris_engine.schemas.services.operations import MemoryQuery, MemoryOpResult
from ciris_engine.schemas.services.graph.memory import MemorySearchFilter
from ..dependencies.auth import require_observer, require_admin, AuthContext

if TYPE_CHECKING:
    import networkx as nx

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
    limit: Optional[int] = Query(100, ge=1, le=1000, description="Maximum number of memories to return"),
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
            limit=limit  # Use the provided limit parameter
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
):
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
    auth: AuthContext = Depends(require_observer)
):
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
            
            # Use wildcard query with type filter
            query = MemoryQuery(
                node_id="*",
                scope=scope,
                type=node_type,
                include_edges=False,
                depth=1
            )
            all_nodes = await memory_service.recall(query)
            
            # Filter by time
            for node in all_nodes:
                node_time = node.attributes.get('created_at') or node.attributes.get('timestamp')
                if node_time:
                    if isinstance(node_time, str):
                        node_time = datetime.fromisoformat(node_time.replace('Z', '+00:00'))
                    if since <= node_time <= now:
                        nodes.append(node)
            
            # Sort by time for timeline layout
            nodes.sort(key=lambda n: n.attributes.get('created_at') or n.attributes.get('timestamp', ''))
        else:
            # Regular query - get nodes with optional type filter
            query = MemoryQuery(
                node_id="*",
                scope=scope,
                type=node_type,
                include_edges=False,
                depth=1
            )
            nodes = await memory_service.recall(query)
        
        # Limit nodes for visualization
        nodes = nodes[:limit]
        
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
                'title': node.attributes.get('title', ''),
                'created_at': node.attributes.get('created_at') or node.attributes.get('timestamp', ''),
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
        attr_count = len([k for k, v in node.attributes.items() if v is not None])
        base_size += min(attr_count * 2, 20)
    
    # Increase size for identity-related nodes
    if node.scope == GraphScope.IDENTITY:
        base_size += 10
    
    return base_size


def _calculate_timeline_layout(G: "nx.DiGraph", nodes: List[GraphNode], width: int, height: int) -> Dict[str, tuple]:
    """Calculate timeline layout with nodes arranged chronologically."""
    pos = {}
    
    # Group nodes by time buckets (hourly)
    time_buckets = {}
    for node in nodes:
        node_time = node.attributes.get('created_at') or node.attributes.get('timestamp', '')
        if node_time:
            if isinstance(node_time, str):
                node_time = datetime.fromisoformat(node_time.replace('Z', '+00:00'))
            
            # Round to hour
            bucket = node_time.replace(minute=0, second=0, microsecond=0)
            if bucket not in time_buckets:
                time_buckets[bucket] = []
            time_buckets[bucket].append(node.id)
    
    # Sort buckets by time
    sorted_buckets = sorted(time_buckets.items())
    
    if not sorted_buckets:
        # Fallback to force layout if no timestamps
        return nx.spring_layout(G)
    
    # Calculate x positions for each time bucket
    x_spacing = (width - 100) / max(len(sorted_buckets) - 1, 1)
    
    for i, (bucket_time, node_ids) in enumerate(sorted_buckets):
        x = 50 + i * x_spacing
        
        # Distribute nodes vertically within each time bucket
        y_spacing = (height - 100) / max(len(node_ids), 1)
        for j, node_id in enumerate(node_ids):
            y = 50 + j * y_spacing + (y_spacing / 2)
            pos[node_id] = (x, y)
    
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
        
        # Add time labels
        now = datetime.now(timezone.utc)
        for i in range(0, hours + 1, max(hours // 6, 1)):
            x = 50 + (i / hours) * (width - 100)
            time_label = (now - timedelta(hours=hours-i)).strftime("%m/%d %H:%M")
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
