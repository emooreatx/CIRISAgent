"""
Memory service endpoints for CIRIS API v1.

The memory service implements the three universal verbs: MEMORIZE, RECALL, FORGET.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from ciris_engine.schemas.api.responses import SuccessResponse, ErrorResponse, ErrorCode
from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphScope
from ciris_engine.schemas.services.operations import MemoryQuery, MemoryOpResult, MemoryRecallResult
from ciris_engine.schemas.services.graph.memory import MemorySearchFilter
from ciris_engine.schemas.runtime.memory import TimeSeriesDataPoint
from ciris_engine.api.dependencies.auth import require_observer, require_admin, AuthContext

router = APIRouter(prefix="/memory", tags=["memory"])

# Request/Response schemas

class MemorizeRequest(BaseModel):
    """Request to memorize a graph node."""
    node: GraphNode = Field(..., description="Graph node to store in memory")

class RecallRequest(BaseModel):
    """Request to recall memories."""
    query: MemoryQuery = Field(..., description="Memory query parameters")

class ForgetRequest(BaseModel):
    """Request to forget a memory."""
    node: GraphNode = Field(..., description="Graph node to remove from memory")

class SearchRequest(BaseModel):
    """Memory search request."""
    query: str = Field(..., description="Text search query")
    filters: Optional[MemorySearchFilter] = Field(None, description="Optional search filters")

class GraphQueryRequest(BaseModel):
    """Advanced graph query request."""
    cypher: str = Field(..., description="Cypher query string")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Query parameters")

class CorrelationRequest(BaseModel):
    """Find correlated memories request."""
    node_id: str = Field(..., description="Node ID to find correlations for")
    correlation_types: Optional[List[str]] = Field(None, description="Types of correlations to find")
    limit: int = Field(10, ge=1, le=100, description="Maximum results")

class TimelineResponse(BaseModel):
    """Timeline view of memories."""
    timeline: List[Dict[str, Any]] = Field(..., description="Memories organized by time")
    start_time: datetime = Field(..., description="Start of timeline")
    end_time: datetime = Field(..., description="End of timeline")
    total_memories: int = Field(..., description="Total memories in range")

class NodeListResponse(BaseModel):
    """List of graph nodes."""
    nodes: List[GraphNode] = Field(..., description="Graph nodes")
    total: int = Field(..., description="Total count")
    offset: int = Field(0, description="Pagination offset")
    limit: int = Field(100, description="Pagination limit")

class EdgeResponse(BaseModel):
    """Graph edge/relationship."""
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    relationship_type: str = Field(..., description="Type of relationship")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Edge properties")

class EdgeListResponse(BaseModel):
    """List of graph edges."""
    edges: List[EdgeResponse] = Field(..., description="Graph edges")
    total: int = Field(..., description="Total count")

# Endpoints

@router.post("/memorize", response_model=SuccessResponse[MemoryOpResult])
async def memorize(
    request: Request,
    body: MemorizeRequest,
    auth: AuthContext = Depends(require_admin)
):
    """
    Store a typed node in graph memory.
    
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

@router.post("/recall", response_model=SuccessResponse[MemoryRecallResult])
async def recall(
    request: Request,
    body: RecallRequest,
    auth: AuthContext = Depends(require_observer)
):
    """
    Query memories with rich filtering.
    
    OBSERVER role can read all memories.
    """
    memory_service = getattr(request.app.state, 'memory_service', None)
    if not memory_service:
        raise HTTPException(status_code=503, detail="Memory service not available")
    
    try:
        nodes = await memory_service.recall(body.query)
        result = MemoryRecallResult(
            nodes=nodes,
            total_count=len(nodes)
        )
        return SuccessResponse(data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/forget", response_model=SuccessResponse[MemoryOpResult])
async def forget(
    request: Request,
    body: ForgetRequest,
    auth: AuthContext = Depends(require_admin)
):
    """
    Remove specific memories.
    
    Requires ADMIN role as this modifies system state.
    """
    memory_service = getattr(request.app.state, 'memory_service', None)
    if not memory_service:
        raise HTTPException(status_code=503, detail="Memory service not available")
    
    try:
        result = await memory_service.forget(body.node)
        return SuccessResponse(data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search", response_model=SuccessResponse[List[GraphNode]])
async def search_memories(
    request: Request,
    q: str = Query(..., description="Search query"),
    scope: Optional[GraphScope] = Query(None, description="Memory scope filter"),
    node_type: Optional[NodeType] = Query(None, description="Node type filter"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Text-based memory search.
    
    Search across all memory scopes using natural language.
    """
    memory_service = getattr(request.app.state, 'memory_service', None)
    if not memory_service:
        raise HTTPException(status_code=503, detail="Memory service not available")
    
    try:
        # Build filters
        filters = None
        if scope or node_type:
            filters = MemorySearchFilter()
            if scope:
                filters.scope = scope
            if node_type:
                filters.node_type = node_type
        
        results = await memory_service.search(q, filters=filters)
        # Limit results
        if len(results) > limit:
            results = results[:limit]
        
        return SuccessResponse(data=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/correlations", response_model=SuccessResponse[List[GraphNode]])
async def find_correlations(
    request: Request,
    node_id: str = Query(..., description="Node ID to find correlations for"),
    types: Optional[List[str]] = Query(None, description="Correlation types"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Find related memories.
    
    Discover memories correlated to a specific node.
    """
    memory_service = getattr(request.app.state, 'memory_service', None)
    if not memory_service:
        raise HTTPException(status_code=503, detail="Memory service not available")
    
    try:
        # Use recall with depth to find connected nodes
        query = MemoryQuery(
            node_id=node_id,
            scope=GraphScope.LOCAL,  # Will search all scopes
            include_edges=True,
            depth=2  # Look for immediate connections
        )
        
        nodes = await memory_service.recall(query)
        
        # Filter to requested limit
        if len(nodes) > limit:
            nodes = nodes[:limit]
        
        return SuccessResponse(data=nodes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/timeline", response_model=SuccessResponse[TimelineResponse])
async def get_timeline(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    scope: Optional[GraphScope] = Query(None, description="Memory scope filter"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Temporal view of memories.
    
    Get memories organized by time buckets.
    """
    memory_service = getattr(request.app.state, 'memory_service', None)
    if not memory_service:
        raise HTTPException(status_code=503, detail="Memory service not available")
    
    try:
        # Get time-series data
        correlation_types = None
        if scope:
            correlation_types = [scope.value]
        
        timeseries = await memory_service.recall_timeseries(
            scope=scope.value if scope else "default",
            hours=hours,
            correlation_types=correlation_types
        )
        
        # Organize into timeline
        now = datetime.now(timezone.utc)
        start_time = datetime.now(timezone.utc).replace(hour=now.hour - hours)
        
        timeline_data = []
        for ts_point in timeseries:
            timeline_data.append({
                "timestamp": ts_point.timestamp,
                "value": ts_point.value,
                "metric": ts_point.metric_name,
                "tags": ts_point.tags
            })
        
        response = TimelineResponse(
            timeline=timeline_data,
            start_time=start_time,
            end_time=now,
            total_memories=len(timeline_data)
        )
        
        return SuccessResponse(data=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/graph/query", response_model=SuccessResponse[List[Dict[str, Any]]])
async def graph_query(
    request: Request,
    body: GraphQueryRequest,
    auth: AuthContext = Depends(require_admin)
):
    """
    Advanced graph queries.
    
    Execute Cypher queries against the memory graph.
    Requires ADMIN role for security.
    """
    memory_service = getattr(request.app.state, 'memory_service', None)
    if not memory_service:
        raise HTTPException(status_code=503, detail="Memory service not available")
    
    try:
        # Check if service supports graph queries
        if not hasattr(memory_service, 'execute_cypher'):
            raise HTTPException(
                status_code=501,
                detail="Graph queries not supported by current memory implementation"
            )
        
        results = await memory_service.execute_cypher(
            body.cypher,
            parameters=body.parameters
        )
        
        return SuccessResponse(data=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/nodes/{node_id}", response_model=SuccessResponse[GraphNode])
async def get_node(
    request: Request,
    node_id: str,
    auth: AuthContext = Depends(require_observer)
):
    """
    Direct node access.
    
    Get a specific node by ID.
    """
    memory_service = getattr(request.app.state, 'memory_service', None)
    if not memory_service:
        raise HTTPException(status_code=503, detail="Memory service not available")
    
    try:
        # Use recall to get specific node
        query = MemoryQuery(
            node_id=node_id,
            scope=GraphScope.LOCAL,  # Will search all scopes
            include_edges=False
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

@router.get("/edges", response_model=SuccessResponse[EdgeListResponse])
async def get_edges(
    request: Request,
    source_id: Optional[str] = Query(None, description="Filter by source node"),
    target_id: Optional[str] = Query(None, description="Filter by target node"),
    relationship_type: Optional[str] = Query(None, description="Filter by relationship type"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Relationship exploration.
    
    Query edges/relationships in the memory graph.
    """
    memory_service = getattr(request.app.state, 'memory_service', None)
    if not memory_service:
        raise HTTPException(status_code=503, detail="Memory service not available")
    
    try:
        # Check if service supports edge queries
        if not hasattr(memory_service, 'get_edges'):
            # Fallback: use node recall with edges
            edges = []
            if source_id:
                query = MemoryQuery(
                    node_id=source_id,
                    scope=GraphScope.LOCAL,
                    include_edges=True,
                    depth=1
                )
                nodes = await memory_service.recall(query)
                # Extract edges from response (implementation specific)
                # This is a simplified version
                for node in nodes:
                    if hasattr(node, 'edges'):
                        for edge in node.edges:
                            edges.append(EdgeResponse(
                                source_id=source_id,
                                target_id=edge.target_id,
                                relationship_type=edge.type,
                                properties=edge.properties or {}
                            ))
        else:
            # Use dedicated edge query method
            edge_results = await memory_service.get_edges(
                source_id=source_id,
                target_id=target_id,
                relationship_type=relationship_type,
                limit=limit
            )
            
            edges = [
                EdgeResponse(
                    source_id=e['source_id'],
                    target_id=e['target_id'],
                    relationship_type=e['type'],
                    properties=e.get('properties', {})
                )
                for e in edge_results
            ]
        
        # Apply limit
        if len(edges) > limit:
            edges = edges[:limit]
        
        response = EdgeListResponse(
            edges=edges,
            total=len(edges)
        )
        
        return SuccessResponse(data=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))