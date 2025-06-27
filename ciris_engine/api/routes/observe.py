"""
Observability Aggregation endpoints for CIRIS API v1.

Cross-service observability views providing unified monitoring and analysis
across all system components.
"""
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
import json
import asyncio
from collections import defaultdict

from ciris_engine.schemas.api.responses import SuccessResponse, ErrorResponse, ErrorCode
from ciris_engine.api.dependencies.auth import require_observer, require_admin, AuthContext
from ciris_engine.schemas.services.visibility import VisibilitySnapshot, ReasoningTrace
from ciris_engine.schemas.services.nodes import AuditEntry
from ciris_engine.schemas.runtime.system_context import TelemetrySummary

router = APIRouter(prefix="/observe", tags=["observability"])

# Request/Response schemas

class ServiceHealth(BaseModel):
    """Health status of a service."""
    service_name: str = Field(..., description="Name of the service")
    status: str = Field(..., description="Health status: healthy|degraded|unhealthy")
    last_check: datetime = Field(..., description="Last health check time")
    error_count: int = Field(0, description="Recent error count")
    latency_ms: Optional[float] = Field(None, description="Average latency")

class SystemMetrics(BaseModel):
    """Aggregated system metrics."""
    cpu_percent: float = Field(..., description="Total CPU usage")
    memory_mb: float = Field(..., description="Total memory usage")
    disk_mb: float = Field(..., description="Total disk usage")
    active_tasks: int = Field(..., description="Active task count")
    message_queue_depth: int = Field(..., description="Total queue depth")
    error_rate: float = Field(..., description="Errors per minute")

class CognitiveMetrics(BaseModel):
    """Agent cognitive metrics."""
    current_state: str = Field(..., description="Current cognitive state")
    state_duration_seconds: float = Field(..., description="Time in current state")
    thoughts_per_minute: float = Field(..., description="Thought generation rate")
    decision_accuracy: float = Field(..., description="Decision success rate")
    reasoning_depth: int = Field(..., description="Average reasoning depth")

class DashboardData(BaseModel):
    """Unified dashboard data."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    services: List[ServiceHealth] = Field(..., description="Service health status")
    system: SystemMetrics = Field(..., description="System resource metrics")
    cognitive: CognitiveMetrics = Field(..., description="Cognitive performance")
    recent_incidents: int = Field(0, description="Incidents in last hour")
    active_deferrals: int = Field(0, description="Pending deferrals")
    llm_usage: Dict[str, float] = Field(default_factory=dict, description="LLM usage by model")

class TraceSpan(BaseModel):
    """Single span in a distributed trace."""
    span_id: str = Field(..., description="Unique span ID")
    parent_id: Optional[str] = Field(None, description="Parent span ID")
    service: str = Field(..., description="Service name")
    operation: str = Field(..., description="Operation name")
    start_time: datetime = Field(..., description="Start timestamp")
    duration_ms: float = Field(..., description="Duration in milliseconds")
    tags: Dict[str, Any] = Field(default_factory=dict, description="Span tags")
    logs: List[Dict[str, Any]] = Field(default_factory=list, description="Span logs")

class DistributedTrace(BaseModel):
    """Complete distributed trace."""
    trace_id: str = Field(..., description="Unique trace ID")
    spans: List[TraceSpan] = Field(..., description="Trace spans")
    total_duration_ms: float = Field(..., description="Total trace duration")
    service_count: int = Field(..., description="Number of services involved")
    error_count: int = Field(0, description="Number of errors in trace")

class TracesResponse(BaseModel):
    """Response containing distributed traces."""
    traces: List[DistributedTrace] = Field(..., description="Recent traces")
    total: int = Field(..., description="Total trace count")

class AggregatedMetric(BaseModel):
    """Aggregated metric across services."""
    metric_name: str = Field(..., description="Metric name")
    value: float = Field(..., description="Current value")
    unit: Optional[str] = Field(None, description="Metric unit")
    trend: str = Field("stable", description="Trend: up|down|stable")
    by_service: Dict[str, float] = Field(default_factory=dict, description="Values by service")

class MetricsResponse(BaseModel):
    """Aggregated metrics response."""
    metrics: List[AggregatedMetric] = Field(..., description="Aggregated metrics")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class LogEntry(BaseModel):
    """Centralized log entry."""
    timestamp: datetime = Field(..., description="Log timestamp")
    level: str = Field(..., description="Log level")
    service: str = Field(..., description="Source service")
    message: str = Field(..., description="Log message")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")

class LogsResponse(BaseModel):
    """Centralized logs response."""
    logs: List[LogEntry] = Field(..., description="Log entries")
    total: int = Field(..., description="Total matching logs")
    has_more: bool = Field(False, description="More logs available")

class ObservabilityQuery(BaseModel):
    """Custom observability query."""
    query_type: str = Field(..., description="Query type: metrics|traces|logs|composite")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Query filters")
    aggregations: List[str] = Field(default_factory=list, description="Aggregations to apply")
    time_range: Optional[Dict[str, datetime]] = Field(None, description="Time range filter")

class QueryResponse(BaseModel):
    """Custom query response."""
    query_type: str = Field(..., description="Query type executed")
    results: List[Dict[str, Any]] = Field(..., description="Query results")
    execution_time_ms: float = Field(..., description="Query execution time")

class StreamConfig(BaseModel):
    """WebSocket stream configuration."""
    include_metrics: bool = Field(True, description="Include metrics updates")
    include_logs: bool = Field(True, description="Include log entries")
    include_traces: bool = Field(True, description="Include trace data")
    include_reasoning: bool = Field(True, description="Include reasoning updates")
    filter_services: Optional[List[str]] = Field(None, description="Filter by services")

# Helper functions

async def _aggregate_service_health(request: Request) -> List[ServiceHealth]:
    """Aggregate health status from all services."""
    health_data = []
    
    # Core services
    services = [
        ('memory_service', 'Memory'),
        ('llm_service', 'LLM'),
        ('audit_service', 'Audit'),
        ('telemetry_service', 'Telemetry'),
        ('config_service', 'Config'),
        ('visibility_service', 'Visibility'),
        ('time_service', 'Time'),
        ('secrets_service', 'Secrets'),
        ('resource_monitor', 'ResourceMonitor'),
        ('authentication_service', 'Authentication'),
        ('wise_authority', 'WiseAuthority'),
        ('incident_management', 'IncidentManagement'),
        ('tsdb_consolidation', 'TSDBConsolidation'),
        ('self_configuration', 'SelfConfiguration'),
        ('adaptive_filter', 'AdaptiveFilter'),
        ('task_scheduler', 'TaskScheduler')
    ]
    
    for service_attr, service_name in services:
        service = getattr(request.app.state, service_attr, None)
        if service:
            # Simple health check based on service existence
            health_data.append(ServiceHealth(
                service_name=service_name,
                status="healthy",
                last_check=datetime.now(timezone.utc),
                error_count=0,
                latency_ms=None
            ))
        else:
            health_data.append(ServiceHealth(
                service_name=service_name,
                status="unhealthy",
                last_check=datetime.now(timezone.utc),
                error_count=1,
                latency_ms=None
            ))
    
    return health_data

async def _aggregate_system_metrics(request: Request) -> SystemMetrics:
    """Aggregate system metrics from various services."""
    # Get resource monitor
    resource_monitor = getattr(request.app.state, 'resource_monitor', None)
    
    # Default metrics
    metrics = SystemMetrics(
        cpu_percent=0.0,
        memory_mb=0.0,
        disk_mb=0.0,
        active_tasks=0,
        message_queue_depth=0,
        error_rate=0.0
    )
    
    if resource_monitor:
        try:
            # Get current resource usage
            usage = await resource_monitor.get_current_usage()
            if usage:
                metrics.cpu_percent = usage.get('cpu_percent', 0.0)
                metrics.memory_mb = usage.get('memory_mb', 0.0)
                metrics.disk_mb = usage.get('disk_mb', 0.0)
        except Exception:
            pass
    
    # Get task scheduler for active tasks
    task_scheduler = getattr(request.app.state, 'task_scheduler', None)
    if task_scheduler:
        try:
            active_tasks = await task_scheduler.get_active_tasks()
            metrics.active_tasks = len(active_tasks) if active_tasks else 0
        except Exception:
            pass
    
    return metrics

async def _aggregate_cognitive_metrics(request: Request) -> CognitiveMetrics:
    """Aggregate cognitive metrics from visibility service."""
    visibility_service = getattr(request.app.state, 'visibility_service', None)
    
    # Default metrics
    metrics = CognitiveMetrics(
        current_state="UNKNOWN",
        state_duration_seconds=0.0,
        thoughts_per_minute=0.0,
        decision_accuracy=1.0,
        reasoning_depth=0
    )
    
    if visibility_service:
        try:
            # Get current snapshot
            snapshot = await visibility_service.get_snapshot()
            if snapshot:
                metrics.current_state = snapshot.cognitive_state
                # Calculate state duration
                if hasattr(snapshot, 'state_entered_at'):
                    duration = datetime.now(timezone.utc) - snapshot.state_entered_at
                    metrics.state_duration_seconds = duration.total_seconds()
                
                # Get reasoning trace for depth
                if snapshot.current_task_id:
                    trace = await visibility_service.get_reasoning_trace(snapshot.current_task_id)
                    if trace and trace.thought_steps:
                        metrics.reasoning_depth = len(trace.thought_steps)
        except Exception:
            pass
    
    return metrics

async def _build_distributed_traces(request: Request, limit: int = 10) -> List[DistributedTrace]:
    """Build distributed traces from audit and telemetry data."""
    audit_service = getattr(request.app.state, 'audit_service', None)
    traces = []
    
    if audit_service:
        try:
            # Get recent audit entries
            recent_entries = await audit_service.query_entries(limit=limit * 5)  # Get more to group
            
            # Group by correlation ID or time window
            trace_groups = defaultdict(list)
            for entry in recent_entries:
                # Use correlation ID if available, otherwise group by minute
                trace_key = entry.context.get('correlation_id', entry.timestamp.strftime('%Y%m%d%H%M'))
                trace_groups[trace_key].append(entry)
            
            # Build traces from groups
            for trace_id, entries in list(trace_groups.items())[:limit]:
                if not entries:
                    continue
                
                # Sort by timestamp
                entries.sort(key=lambda e: e.timestamp)
                
                # Build spans
                spans = []
                for i, entry in enumerate(entries):
                    span = TraceSpan(
                        span_id=f"{trace_id}_span_{i}",
                        parent_id=f"{trace_id}_span_{i-1}" if i > 0 else None,
                        service=entry.actor.split('.')[0] if '.' in entry.actor else entry.actor,
                        operation=entry.action,
                        start_time=entry.timestamp,
                        duration_ms=10.0,  # Default duration
                        tags={"action": entry.action, "actor": entry.actor},
                        logs=[{"timestamp": entry.timestamp, "message": f"Executed {entry.action}"}]
                    )
                    spans.append(span)
                
                # Calculate total duration
                if len(entries) > 1:
                    total_duration = (entries[-1].timestamp - entries[0].timestamp).total_seconds() * 1000
                else:
                    total_duration = 10.0
                
                trace = DistributedTrace(
                    trace_id=trace_id,
                    spans=spans,
                    total_duration_ms=total_duration,
                    service_count=len(set(s.service for s in spans)),
                    error_count=sum(1 for e in entries if 'error' in e.action.lower())
                )
                traces.append(trace)
        except Exception:
            pass
    
    return traces

async def _aggregate_metrics(request: Request) -> List[AggregatedMetric]:
    """Aggregate metrics from all services."""
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    metrics = []
    
    if telemetry_service:
        try:
            # Get current metrics
            current_metrics = await telemetry_service.get_current_metrics()
            
            # Aggregate common metrics
            metric_aggregates = defaultdict(lambda: {'values': [], 'unit': None})
            
            for metric_name, metric_data in current_metrics.items():
                base_name = metric_name.split('.')[0]  # Group by base metric name
                metric_aggregates[base_name]['values'].append(metric_data.get('value', 0))
                metric_aggregates[base_name]['unit'] = metric_data.get('unit')
            
            # Build aggregated metrics
            for base_name, data in metric_aggregates.items():
                if data['values']:
                    avg_value = sum(data['values']) / len(data['values'])
                    
                    # Determine trend (simplified)
                    trend = "stable"
                    
                    metric = AggregatedMetric(
                        metric_name=base_name,
                        value=avg_value,
                        unit=data['unit'],
                        trend=trend,
                        by_service={}  # Could break down by service if needed
                    )
                    metrics.append(metric)
        except Exception:
            pass
    
    return metrics

async def _get_centralized_logs(
    request: Request,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    level: Optional[str] = None,
    service: Optional[str] = None,
    limit: int = 100
) -> LogsResponse:
    """Get centralized logs from audit service."""
    audit_service = getattr(request.app.state, 'audit_service', None)
    logs = []
    
    if audit_service:
        try:
            # Query audit entries as logs
            entries = await audit_service.query_entries(
                start_time=start_time,
                end_time=end_time,
                limit=limit
            )
            
            for entry in entries:
                # Convert audit entry to log format
                log_level = "INFO"
                if "error" in entry.action.lower():
                    log_level = "ERROR"
                elif "warning" in entry.action.lower():
                    log_level = "WARNING"
                
                # Filter by level if specified
                if level and log_level != level.upper():
                    continue
                
                # Filter by service if specified
                log_service = entry.actor.split('.')[0] if '.' in entry.actor else entry.actor
                if service and log_service.lower() != service.lower():
                    continue
                
                log = LogEntry(
                    timestamp=entry.timestamp,
                    level=log_level,
                    service=log_service,
                    message=f"{entry.action}: {entry.context.get('description', '')}",
                    context=entry.context
                )
                logs.append(log)
        except Exception:
            pass
    
    return LogsResponse(
        logs=logs[:limit],
        total=len(logs),
        has_more=len(logs) > limit
    )

# Endpoints

@router.get("/dashboard", response_model=SuccessResponse[DashboardData])
async def get_dashboard(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get unified dashboard data aggregating multiple services.
    
    Provides a comprehensive view of system health, performance, and status.
    """
    # Aggregate data from various services
    services = await _aggregate_service_health(request)
    system = await _aggregate_system_metrics(request)
    cognitive = await _aggregate_cognitive_metrics(request)
    
    # Get incident count
    incident_service = getattr(request.app.state, 'incident_management', None)
    recent_incidents = 0
    if incident_service:
        try:
            # Get incidents from last hour
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            incidents = await incident_service.get_incidents(start_time=one_hour_ago)
            recent_incidents = len(incidents) if incidents else 0
        except Exception:
            pass
    
    # Get deferral count
    wise_authority = getattr(request.app.state, 'wise_authority', None)
    active_deferrals = 0
    if wise_authority:
        try:
            deferrals = await wise_authority.get_pending_deferrals()
            active_deferrals = len(deferrals) if deferrals else 0
        except Exception:
            pass
    
    # Get LLM usage
    llm_service = getattr(request.app.state, 'llm_service', None)
    llm_usage = {}
    if llm_service:
        try:
            usage = await llm_service.get_usage_stats()
            if usage:
                llm_usage = usage.get('by_model', {})
        except Exception:
            pass
    
    dashboard = DashboardData(
        services=services,
        system=system,
        cognitive=cognitive,
        recent_incidents=recent_incidents,
        active_deferrals=active_deferrals,
        llm_usage=llm_usage
    )
    
    return SuccessResponse(data=dashboard)

@router.get("/traces", response_model=SuccessResponse[TracesResponse])
async def get_traces(
    request: Request,
    auth: AuthContext = Depends(require_observer),
    limit: int = Query(10, ge=1, le=100, description="Maximum traces to return"),
    service: Optional[str] = Query(None, description="Filter by service")
):
    """
    Get distributed traces across services.
    
    Shows how requests flow through the system and where time is spent.
    """
    traces = await _build_distributed_traces(request, limit)
    
    # Filter by service if specified
    if service:
        traces = [t for t in traces if any(s.service.lower() == service.lower() for s in t.spans)]
    
    response = TracesResponse(
        traces=traces,
        total=len(traces)
    )
    
    return SuccessResponse(data=response)

@router.get("/metrics", response_model=SuccessResponse[MetricsResponse])
async def get_aggregated_metrics(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get aggregated metrics from all services.
    
    Provides system-wide performance and resource metrics.
    """
    metrics = await _aggregate_metrics(request)
    
    response = MetricsResponse(
        metrics=metrics,
        timestamp=datetime.now(timezone.utc)
    )
    
    return SuccessResponse(data=response)

@router.get("/logs", response_model=SuccessResponse[LogsResponse])
async def get_centralized_logs(
    request: Request,
    auth: AuthContext = Depends(require_observer),
    start_time: Optional[datetime] = Query(None, description="Start of time range"),
    end_time: Optional[datetime] = Query(None, description="End of time range"),
    level: Optional[str] = Query(None, description="Log level filter"),
    service: Optional[str] = Query(None, description="Service filter"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum logs to return")
):
    """
    Get centralized logs from all services.
    
    Provides a unified view of system activity and errors.
    """
    response = await _get_centralized_logs(
        request,
        start_time=start_time,
        end_time=end_time,
        level=level,
        service=service,
        limit=limit
    )
    
    return SuccessResponse(data=response)

@router.post("/query", response_model=SuccessResponse[QueryResponse])
async def execute_query(
    request: Request,
    query: ObservabilityQuery,
    auth: AuthContext = Depends(require_observer)
):
    """
    Execute a custom observability query.
    
    Allows complex queries across multiple data sources.
    """
    start_time = datetime.now(timezone.utc)
    results = []
    
    # Execute based on query type
    if query.query_type == "metrics":
        metrics = await _aggregate_metrics(request)
        results = [m.model_dump() for m in metrics]
    
    elif query.query_type == "traces":
        traces = await _build_distributed_traces(request, limit=50)
        results = [t.model_dump() for t in traces]
    
    elif query.query_type == "logs":
        logs_response = await _get_centralized_logs(request, limit=100)
        results = [log.model_dump() for log in logs_response.logs]
    
    elif query.query_type == "composite":
        # Composite query combining multiple data sources
        dashboard = await get_dashboard(request, auth)
        results = [dashboard.data.model_dump()]
    
    # Apply filters if provided
    if query.filters:
        # Simple filter implementation
        for key, value in query.filters.items():
            results = [r for r in results if key in r and r[key] == value]
    
    # Apply time range filter
    if query.time_range and 'start' in query.time_range and 'end' in query.time_range:
        start = query.time_range['start']
        end = query.time_range['end']
        results = [
            r for r in results
            if 'timestamp' in r and start <= r['timestamp'] <= end
        ]
    
    execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
    
    response = QueryResponse(
        query_type=query.query_type,
        results=results,
        execution_time_ms=execution_time
    )
    
    return SuccessResponse(data=response)

@router.websocket("/stream")
async def observability_stream(
    websocket: WebSocket,
    api_key: Optional[str] = Query(None, description="API key for authentication")
):
    """
    Real-time observability stream via WebSocket.
    
    Streams live updates from all observability sources.
    """
    await websocket.accept()
    
    # Simple auth check
    if not api_key:
        await websocket.send_json({
            "type": "error",
            "message": "Authentication required"
        })
        await websocket.close()
        return
    
    # Get stream config
    try:
        config_data = await websocket.receive_json()
        config = StreamConfig(**config_data)
    except Exception:
        config = StreamConfig()  # Use defaults
    
    try:
        while True:
            # Send periodic updates
            if config.include_metrics:
                metrics = await _aggregate_metrics(websocket.app.state)
                await websocket.send_json({
                    "type": "metrics",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": [m.model_dump() for m in metrics]
                })
            
            # Send system status
            if config.include_metrics:
                system = await _aggregate_system_metrics(websocket.app.state)
                await websocket.send_json({
                    "type": "system",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": system.model_dump()
                })
            
            # Send cognitive state
            if config.include_reasoning:
                cognitive = await _aggregate_cognitive_metrics(websocket.app.state)
                await websocket.send_json({
                    "type": "cognitive",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": cognitive.model_dump()
                })
            
            # Wait before next update
            await asyncio.sleep(5)  # Update every 5 seconds
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
        await websocket.close()