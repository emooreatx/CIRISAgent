"""
Telemetry & Observability endpoints for CIRIS API v1.

Consolidated metrics, traces, logs, and insights from all system components.
"""
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends, Query, WebSocket
from pydantic import BaseModel, Field, field_serializer
from collections import defaultdict

from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.schemas.runtime.system_context import TelemetrySummary
from ciris_engine.schemas.services.visibility import VisibilitySnapshot, ReasoningTrace, ThoughtStep
from ciris_engine.api.dependencies.auth import require_observer, require_admin, AuthContext

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

# Request/Response schemas

class MetricData(BaseModel):
    """Single metric data point."""
    timestamp: datetime = Field(..., description="When metric was recorded")
    value: float = Field(..., description="Metric value")
    tags: Dict[str, str] = Field(default_factory=dict, description="Metric tags")
    
    @field_serializer('timestamp')
    def serialize_timestamp(self, timestamp: datetime, _info):
        return timestamp.isoformat() if timestamp else None

class MetricSeries(BaseModel):
    """Time series data for a metric."""
    metric_name: str = Field(..., description="Name of the metric")
    data_points: List[MetricData] = Field(..., description="Time series data")
    unit: Optional[str] = Field(None, description="Metric unit")
    description: Optional[str] = Field(None, description="Metric description")

class SystemOverview(BaseModel):
    """System overview combining all observability data."""
    # Core metrics
    uptime_seconds: float = Field(..., description="System uptime")
    cognitive_state: str = Field(..., description="Current cognitive state")
    messages_processed_24h: int = Field(0, description="Messages in last 24 hours")
    thoughts_processed_24h: int = Field(0, description="Thoughts in last 24 hours")
    tasks_completed_24h: int = Field(0, description="Tasks completed in last 24 hours")
    errors_24h: int = Field(0, description="Errors in last 24 hours")
    
    # Resource usage
    tokens_per_hour: float = Field(0.0, description="Average tokens per hour")
    cost_per_hour_cents: float = Field(0.0, description="Average cost per hour in cents")
    carbon_per_hour_grams: float = Field(0.0, description="Carbon footprint per hour")
    memory_mb: float = Field(0.0, description="Current memory usage")
    cpu_percent: float = Field(0.0, description="Current CPU usage")
    
    # Service health
    healthy_services: int = Field(0, description="Number of healthy services")
    degraded_services: int = Field(0, description="Number of degraded services")
    error_rate_percent: float = Field(0.0, description="System error rate")
    
    # Agent activity
    current_task: Optional[str] = Field(None, description="Current task description")
    reasoning_depth: int = Field(0, description="Current reasoning depth")
    active_deferrals: int = Field(0, description="Pending WA deferrals")
    recent_incidents: int = Field(0, description="Incidents in last hour")

class DetailedMetric(BaseModel):
    """Detailed metric information."""
    name: str = Field(..., description="Metric name")
    current_value: float = Field(..., description="Current value")
    unit: Optional[str] = Field(None, description="Metric unit")
    trend: str = Field("stable", description="Trend: up|down|stable")
    hourly_average: float = Field(0.0, description="Average over last hour")
    daily_average: float = Field(0.0, description="Average over last day")
    by_service: Dict[str, float] = Field(default_factory=dict, description="Values by service")
    recent_data: List[MetricData] = Field(default_factory=list, description="Recent data points")

class MetricsResponse(BaseModel):
    """Detailed metrics response."""
    metrics: List[DetailedMetric] = Field(..., description="Detailed metrics")
    timestamp: datetime = Field(..., description="Response timestamp")
    
    @field_serializer('timestamp')
    def serialize_timestamp(self, timestamp: datetime, _info):
        return timestamp.isoformat() if timestamp else None

class ReasoningTraceData(BaseModel):
    """Reasoning trace information."""
    trace_id: str = Field(..., description="Unique trace ID")
    task_id: Optional[str] = Field(None, description="Associated task ID")
    task_description: Optional[str] = Field(None, description="Task description")
    start_time: datetime = Field(..., description="Trace start time")
    duration_ms: float = Field(..., description="Total duration")
    thought_count: int = Field(0, description="Number of thoughts")
    decision_count: int = Field(0, description="Number of decisions")
    reasoning_depth: int = Field(0, description="Maximum reasoning depth")
    thoughts: List[Dict[str, Any]] = Field(default_factory=list, description="Thought steps")
    outcome: Optional[str] = Field(None, description="Final outcome")
    
    @field_serializer('start_time')
    def serialize_timestamp(self, timestamp: datetime, _info):
        return timestamp.isoformat() if timestamp else None

class TracesResponse(BaseModel):
    """Reasoning traces response."""
    traces: List[ReasoningTraceData] = Field(..., description="Recent reasoning traces")
    total: int = Field(..., description="Total trace count")
    has_more: bool = Field(False, description="More traces available")

class LogEntry(BaseModel):
    """System log entry."""
    timestamp: datetime = Field(..., description="Log timestamp")
    level: str = Field(..., description="Log level: DEBUG|INFO|WARNING|ERROR|CRITICAL")
    service: str = Field(..., description="Source service")
    message: str = Field(..., description="Log message")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    trace_id: Optional[str] = Field(None, description="Associated trace ID")
    
    @field_serializer('timestamp')
    def serialize_timestamp(self, timestamp: datetime, _info):
        return timestamp.isoformat() if timestamp else None

class LogsResponse(BaseModel):
    """System logs response."""
    logs: List[LogEntry] = Field(..., description="Log entries")
    total: int = Field(..., description="Total matching logs")
    has_more: bool = Field(False, description="More logs available")

class TelemetryQuery(BaseModel):
    """Custom telemetry query."""
    query_type: str = Field(..., description="Query type: metrics|traces|logs|incidents|insights")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Query filters")
    aggregations: Optional[List[str]] = Field(None, description="Aggregations to apply")
    start_time: Optional[datetime] = Field(None, description="Query start time")
    end_time: Optional[datetime] = Field(None, description="Query end time")
    limit: int = Field(100, ge=1, le=1000, description="Result limit")
    
    @field_serializer('start_time', 'end_time')
    def serialize_times(self, dt: Optional[datetime], _info):
        return dt.isoformat() if dt else None

class QueryResponse(BaseModel):
    """Custom query response."""
    query_type: str = Field(..., description="Query type executed")
    results: List[Dict[str, Any]] = Field(..., description="Query results")
    total: int = Field(..., description="Total results found")
    execution_time_ms: float = Field(..., description="Query execution time")

# Helper functions

async def _get_system_overview(request: Request) -> SystemOverview:
    """Build comprehensive system overview from all services."""
    # Get core services
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    visibility_service = getattr(request.app.state, 'visibility_service', None)
    time_service = getattr(request.app.state, 'time_service', None)
    resource_monitor = getattr(request.app.state, 'resource_monitor', None)
    incident_service = getattr(request.app.state, 'incident_management', None)
    wise_authority = getattr(request.app.state, 'wise_authority', None)
    
    # Initialize overview
    overview = SystemOverview(
        uptime_seconds=0.0,
        cognitive_state="UNKNOWN"
    )
    
    # Get uptime from time service
    if time_service:
        try:
            uptime = await time_service.get_uptime()
            overview.uptime_seconds = uptime.total_seconds()
        except:
            pass
    
    # Get telemetry summary if available
    if telemetry_service and hasattr(telemetry_service, 'get_telemetry_summary'):
        try:
            summary = await telemetry_service.get_telemetry_summary()
            overview.messages_processed_24h = summary.messages_processed_24h
            overview.thoughts_processed_24h = summary.thoughts_processed_24h
            overview.tasks_completed_24h = summary.tasks_completed_24h
            overview.errors_24h = summary.errors_24h
            overview.tokens_per_hour = summary.tokens_per_hour
            overview.cost_per_hour_cents = summary.cost_per_hour_cents
            overview.carbon_per_hour_grams = summary.carbon_per_hour_grams
            overview.error_rate_percent = summary.error_rate_percent
        except:
            pass
    
    # Get cognitive state from visibility
    if visibility_service:
        try:
            snapshot = await visibility_service.get_snapshot()
            if snapshot:
                overview.cognitive_state = snapshot.cognitive_state
                overview.reasoning_depth = snapshot.reasoning_depth
                if snapshot.current_task:
                    overview.current_task = snapshot.current_task.description
        except:
            pass
    
    # Get resource usage
    if resource_monitor:
        try:
            usage = await resource_monitor.get_current_usage()
            if usage:
                overview.memory_mb = usage.get('memory_mb', 0.0)
                overview.cpu_percent = usage.get('cpu_percent', 0.0)
        except:
            pass
    
    # Count healthy services
    services = [
        'memory_service', 'llm_service', 'audit_service', 'telemetry_service',
        'config_service', 'visibility_service', 'time_service', 'secrets_service',
        'resource_monitor', 'authentication_service', 'wise_authority',
        'incident_management', 'tsdb_consolidation', 'self_configuration',
        'adaptive_filter', 'task_scheduler', 'initialization_service',
        'shutdown_service', 'runtime_control'
    ]
    
    healthy = 0
    degraded = 0
    for service_attr in services:
        if getattr(request.app.state, service_attr, None):
            healthy += 1
        else:
            degraded += 1
    
    overview.healthy_services = healthy
    overview.degraded_services = degraded
    
    # Get incident count
    if incident_service:
        try:
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            incidents = await incident_service.get_incidents(start_time=one_hour_ago)
            overview.recent_incidents = len(incidents) if incidents else 0
        except:
            pass
    
    # Get deferral count
    if wise_authority:
        try:
            deferrals = await wise_authority.get_pending_deferrals()
            overview.active_deferrals = len(deferrals) if deferrals else 0
        except:
            pass
    
    return overview

# Endpoints

@router.get("/overview", response_model=SuccessResponse[SystemOverview])
async def get_telemetry_overview(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    System metrics summary.
    
    Comprehensive overview combining telemetry, visibility, incidents, and resource usage.
    """
    try:
        overview = await _get_system_overview(request)
        return SuccessResponse(data=overview)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics", response_model=SuccessResponse[MetricsResponse])
async def get_detailed_metrics(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Detailed metrics.
    
    Get detailed metrics with trends and breakdowns by service.
    """
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    if not telemetry_service:
        raise HTTPException(status_code=503, detail="Telemetry service not available")
    
    try:
        # Common metrics to query
        metric_names = [
            "messages_processed",
            "thoughts_processed", 
            "tasks_completed",
            "errors",
            "tokens_consumed",
            "api_requests",
            "memory_operations",
            "llm_calls",
            "deferrals_created",
            "incidents_detected"
        ]
        
        metrics = []
        now = datetime.now(timezone.utc)
        
        for metric_name in metric_names:
            if hasattr(telemetry_service, 'query_metrics'):
                # Get last 24 hours of data
                day_ago = now - timedelta(hours=24)
                hour_ago = now - timedelta(hours=1)
                
                # Get hourly data
                hourly_data = await telemetry_service.query_metrics(
                    metric_name=metric_name,
                    start_time=hour_ago,
                    end_time=now
                )
                
                # Get daily data
                daily_data = await telemetry_service.query_metrics(
                    metric_name=metric_name,
                    start_time=day_ago,
                    end_time=now
                )
                
                if hourly_data or daily_data:
                    # Calculate averages and trends
                    hourly_values = [dp.get('value', 0.0) for dp in hourly_data] if hourly_data else [0.0]
                    daily_values = [dp.get('value', 0.0) for dp in daily_data] if daily_data else [0.0]
                    
                    hourly_avg = sum(hourly_values) / len(hourly_values) if hourly_values else 0.0
                    daily_avg = sum(daily_values) / len(daily_values) if daily_values else 0.0
                    current_value = hourly_values[-1] if hourly_values else 0.0
                    
                    # Determine trend
                    trend = "stable"
                    if len(hourly_values) > 1:
                        recent_avg = sum(hourly_values[-5:]) / len(hourly_values[-5:])
                        older_avg = sum(hourly_values[:-5]) / len(hourly_values[:-5]) if len(hourly_values) > 5 else hourly_values[0]
                        if recent_avg > older_avg * 1.1:
                            trend = "up"
                        elif recent_avg < older_avg * 0.9:
                            trend = "down"
                    
                    # Get unit from metric name
                    unit = None
                    if "tokens" in metric_name:
                        unit = "tokens"
                    elif "time" in metric_name or "latency" in metric_name:
                        unit = "ms"
                    elif "percent" in metric_name or "rate" in metric_name:
                        unit = "%"
                    
                    metric = DetailedMetric(
                        name=metric_name,
                        current_value=current_value,
                        unit=unit,
                        trend=trend,
                        hourly_average=hourly_avg,
                        daily_average=daily_avg,
                        by_service={},  # Could aggregate by service if tags available
                        recent_data=[
                            MetricData(
                                timestamp=dp.get('timestamp', now),
                                value=dp.get('value', 0.0),
                                tags=dp.get('tags', {})
                            )
                            for dp in (hourly_data[-10:] if hourly_data else [])
                        ]
                    )
                    metrics.append(metric)
        
        response = MetricsResponse(
            metrics=metrics,
            timestamp=now
        )
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/traces", response_model=SuccessResponse[TracesResponse])
async def get_reasoning_traces(
    request: Request,
    auth: AuthContext = Depends(require_observer),
    limit: int = Query(10, ge=1, le=100, description="Maximum traces to return"),
    start_time: Optional[datetime] = Query(None, description="Start of time range"),
    end_time: Optional[datetime] = Query(None, description="End of time range")
):
    """
    Reasoning traces.
    
    Get reasoning traces showing agent thought processes and decision-making.
    """
    visibility_service = getattr(request.app.state, 'visibility_service', None)
    audit_service = getattr(request.app.state, 'audit_service', None)
    
    traces = []
    
    # Try to get from visibility service first
    if visibility_service:
        try:
            # Get recent task history
            if hasattr(visibility_service, 'get_task_history'):
                task_history = await visibility_service.get_task_history(limit=limit)
                
                for task in task_history:
                    # Get reasoning trace for each task
                    if hasattr(visibility_service, 'get_reasoning_trace'):
                        trace = await visibility_service.get_reasoning_trace(task.task_id)
                        if trace:
                            trace_data = ReasoningTraceData(
                                trace_id=f"trace_{task.task_id}",
                                task_id=task.task_id,
                                task_description=task.description,
                                start_time=task.created_at,
                                duration_ms=(task.completed_at - task.created_at).total_seconds() * 1000 if task.completed_at else 0,
                                thought_count=len(trace.thought_steps),
                                decision_count=len(trace.decisions) if hasattr(trace, 'decisions') else 0,
                                reasoning_depth=trace.max_depth,
                                thoughts=[
                                    {
                                        "step": i,
                                        "content": thought.content,
                                        "timestamp": thought.timestamp.isoformat(),
                                        "depth": thought.depth
                                    }
                                    for i, thought in enumerate(trace.thought_steps)
                                ],
                                outcome=trace.outcome if hasattr(trace, 'outcome') else None
                            )
                            traces.append(trace_data)
            
            # If no task history, try current reasoning
            if not traces and hasattr(visibility_service, 'get_current_reasoning'):
                current = await visibility_service.get_current_reasoning()
                if current:
                    trace_data = ReasoningTraceData(
                        trace_id="trace_current",
                        task_id=current.get('task_id'),
                        task_description=current.get('task_description'),
                        start_time=datetime.now(timezone.utc),
                        duration_ms=0,
                        thought_count=len(current.get('thoughts', [])),
                        decision_count=0,
                        reasoning_depth=current.get('depth', 0),
                        thoughts=current.get('thoughts', [])
                    )
                    traces.append(trace_data)
        except:
            pass
    
    # Fallback to audit-based traces
    if not traces and audit_service:
        try:
            # Query audit entries related to reasoning
            entries = await audit_service.query_entries(
                action_prefix="THINK",
                start_time=start_time,
                end_time=end_time,
                limit=limit * 10  # Get more to group
            )
            
            # Group by correlation ID or time window
            trace_groups = defaultdict(list)
            for entry in entries:
                trace_key = entry.context.get('task_id', entry.timestamp.strftime('%Y%m%d%H%M'))
                trace_groups[trace_key].append(entry)
            
            # Build traces from groups
            for trace_id, entries in list(trace_groups.items())[:limit]:
                if entries:
                    entries.sort(key=lambda e: e.timestamp)
                    
                    trace_data = ReasoningTraceData(
                        trace_id=f"trace_{trace_id}",
                        task_id=trace_id if trace_id != entries[0].timestamp.strftime('%Y%m%d%H%M') else None,
                        start_time=entries[0].timestamp,
                        duration_ms=(entries[-1].timestamp - entries[0].timestamp).total_seconds() * 1000,
                        thought_count=len(entries),
                        decision_count=sum(1 for e in entries if 'decision' in e.action.lower()),
                        reasoning_depth=max(e.context.get('depth', 0) for e in entries),
                        thoughts=[
                            {
                                "step": i,
                                "content": e.context.get('thought', e.action),
                                "timestamp": e.timestamp.isoformat()
                            }
                            for i, e in enumerate(entries)
                        ]
                    )
                    traces.append(trace_data)
        except:
            pass
    
    response = TracesResponse(
        traces=traces,
        total=len(traces),
        has_more=len(traces) == limit
    )
    
    return SuccessResponse(data=response)

@router.get("/logs", response_model=SuccessResponse[LogsResponse])
async def get_system_logs(
    request: Request,
    auth: AuthContext = Depends(require_observer),
    start_time: Optional[datetime] = Query(None, description="Start of time range"),
    end_time: Optional[datetime] = Query(None, description="End of time range"),
    level: Optional[str] = Query(None, description="Log level filter"),
    service: Optional[str] = Query(None, description="Service filter"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum logs to return")
):
    """
    System logs.
    
    Get system logs from all services with filtering capabilities.
    """
    audit_service = getattr(request.app.state, 'audit_service', None)
    logs = []
    
    if audit_service:
        try:
            # Query audit entries as logs
            entries = await audit_service.query_entries(
                start_time=start_time,
                end_time=end_time,
                limit=limit * 2  # Get extra for filtering
            )
            
            for entry in entries:
                # Determine log level from action
                log_level = "INFO"
                if "error" in entry.action.lower() or "fail" in entry.action.lower():
                    log_level = "ERROR"
                elif "warning" in entry.action.lower() or "warn" in entry.action.lower():
                    log_level = "WARNING"
                elif "debug" in entry.action.lower():
                    log_level = "DEBUG"
                elif "critical" in entry.action.lower() or "fatal" in entry.action.lower():
                    log_level = "CRITICAL"
                
                # Filter by level if specified
                if level and log_level != level.upper():
                    continue
                
                # Extract service from actor
                log_service = entry.actor.split('.')[0] if '.' in entry.actor else entry.actor
                
                # Filter by service if specified
                if service and log_service.lower() != service.lower():
                    continue
                
                # Build log entry
                log = LogEntry(
                    timestamp=entry.timestamp,
                    level=log_level,
                    service=log_service,
                    message=f"{entry.action}: {entry.context.get('description', '')}".strip(': '),
                    context=entry.context,
                    trace_id=entry.context.get('trace_id') or entry.context.get('correlation_id')
                )
                logs.append(log)
                
                if len(logs) >= limit:
                    break
        except Exception:
            pass
    
    # Add some system logs if available
    if len(logs) < limit:
        # Could query actual log files or logging service here
        pass
    
    response = LogsResponse(
        logs=logs[:limit],
        total=len(logs),
        has_more=len(logs) > limit
    )
    
    return SuccessResponse(data=response)

@router.post("/query", response_model=SuccessResponse[QueryResponse])
async def query_telemetry(
    request: Request,
    query: TelemetryQuery,
    auth: AuthContext = Depends(require_admin)
):
    """
    Custom telemetry queries.
    
    Execute custom queries against telemetry data including metrics, traces, logs, incidents, and insights.
    Requires ADMIN role.
    """
    start_time = datetime.now(timezone.utc)
    results = []
    
    # Get services
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    visibility_service = getattr(request.app.state, 'visibility_service', None)
    audit_service = getattr(request.app.state, 'audit_service', None)
    incident_service = getattr(request.app.state, 'incident_management', None)
    
    try:
        if query.query_type == "metrics":
            # Query metrics
            if telemetry_service and hasattr(telemetry_service, 'query_metrics'):
                for filter_key, filter_value in query.filters.items():
                    if filter_key == "metric_names" and isinstance(filter_value, list):
                        for metric_name in filter_value:
                            data_points = await telemetry_service.query_metrics(
                                metric_name=metric_name,
                                start_time=query.start_time,
                                end_time=query.end_time
                            )
                            if data_points:
                                results.append({
                                    "metric_name": metric_name,
                                    "data_points": data_points,
                                    "count": len(data_points)
                                })
        
        elif query.query_type == "traces":
            # Query reasoning traces
            if visibility_service:
                # Get traces based on filters
                trace_limit = query.filters.get('limit', query.limit)
                traces = []
                
                if hasattr(visibility_service, 'query_traces'):
                    traces = await visibility_service.query_traces(
                        start_time=query.start_time,
                        end_time=query.end_time,
                        limit=trace_limit
                    )
                
                for trace in traces:
                    results.append({
                        "trace_id": trace.trace_id,
                        "task_id": trace.task_id,
                        "duration_ms": trace.duration_ms,
                        "thought_count": trace.thought_count
                    })
        
        elif query.query_type == "logs":
            # Query logs
            if audit_service:
                log_entries = await audit_service.query_entries(
                    start_time=query.start_time,
                    end_time=query.end_time,
                    limit=query.limit
                )
                
                for entry in log_entries:
                    # Apply filters
                    if query.filters:
                        if 'service' in query.filters and entry.actor != query.filters['service']:
                            continue
                        if 'level' in query.filters:
                            # Infer level from action
                            if 'error' in entry.action.lower() and query.filters['level'].upper() != 'ERROR':
                                continue
                    
                    results.append({
                        "timestamp": entry.timestamp.isoformat(),
                        "service": entry.actor,
                        "action": entry.action,
                        "context": entry.context
                    })
        
        elif query.query_type == "incidents":
            # Query incidents
            if incident_service:
                incidents = await incident_service.query_incidents(
                    start_time=query.start_time,
                    end_time=query.end_time,
                    severity=query.filters.get('severity'),
                    status=query.filters.get('status')
                )
                
                for incident in incidents:
                    results.append({
                        "incident_id": incident.id,
                        "severity": incident.severity,
                        "status": incident.status,
                        "description": incident.description,
                        "created_at": getattr(incident, 'created_at', incident.detected_at).isoformat()
                    })
        
        elif query.query_type == "insights":
            # Query adaptation insights
            if incident_service and hasattr(incident_service, 'get_insights'):
                insights = await incident_service.get_insights(
                    start_time=query.start_time,
                    end_time=query.end_time,
                    limit=query.limit
                )
                
                for insight in insights:
                    results.append({
                        "insight_id": insight.id,
                        "insight_type": insight.insight_type,
                        "summary": insight.summary,
                        "details": insight.details,
                        "created_at": getattr(insight, 'created_at', insight.analysis_timestamp).isoformat()
                    })
        
        # Apply aggregations if specified
        if query.aggregations:
            for agg in query.aggregations:
                if agg == "count":
                    results = [{"aggregation": "count", "value": len(results)}]
                elif agg == "group_by_service" and query.query_type == "logs":
                    # Group logs by service
                    grouped = defaultdict(int)
                    for r in results:
                        grouped[r.get('service', 'unknown')] += 1
                    results = [{"service": k, "count": v} for k, v in grouped.items()]
        
        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        response = QueryResponse(
            query_type=query.query_type,
            results=results[:query.limit],
            total=len(results),
            execution_time_ms=execution_time
        )
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import asyncio
import logging
logger = logging.getLogger(__name__)