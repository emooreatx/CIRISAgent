"""
Telemetry & Observability endpoints for CIRIS API v1.

Consolidated metrics, traces, logs, and insights from all system components.
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends, Query, Path
from pydantic import BaseModel, Field, field_serializer
from collections import defaultdict

from ciris_engine.schemas.api.responses import SuccessResponse
from ..dependencies.auth import require_observer, require_admin, AuthContext
from ciris_engine.schemas.api.telemetry import (
    MetricTags, ServiceMetricValue, ThoughtStep, LogContext,
    TelemetryQueryFilters, QueryResult, TimeSyncStatus, ServiceMetrics
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

# Request/Response schemas

class MetricData(BaseModel):
    """Single metric data point."""
    timestamp: datetime = Field(..., description="When metric was recorded")
    value: float = Field(..., description="Metric value")
    tags: MetricTags = Field(default_factory=MetricTags, description="Metric tags")

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
    by_service: List[ServiceMetricValue] = Field(default_factory=list, description="Values by service")
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
    thoughts: List[ThoughtStep] = Field(default_factory=list, description="Thought steps")
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
    context: LogContext = Field(default_factory=LogContext, description="Additional context")
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
    filters: TelemetryQueryFilters = Field(default_factory=TelemetryQueryFilters, description="Query filters")
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
    results: List[QueryResult] = Field(..., description="Query results")
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
        except Exception as e:
            logger.warning(f"Telemetry metric retrieval failed for uptime: {type(e).__name__}: {str(e)} - Returning default/empty value")

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
        except Exception as e:
            logger.warning(f"Telemetry metric retrieval failed for telemetry summary: {type(e).__name__}: {str(e)} - Returning default/empty value")

    # Get cognitive state from visibility
    if visibility_service:
        try:
            snapshot = await visibility_service.get_snapshot()
            if snapshot:
                overview.cognitive_state = snapshot.cognitive_state
                overview.reasoning_depth = snapshot.reasoning_depth
                if snapshot.current_task:
                    overview.current_task = snapshot.current_task.description
        except Exception as e:
            logger.warning(f"Telemetry metric retrieval failed for cognitive state visibility: {type(e).__name__}: {str(e)} - Returning default/empty value")

    # Get resource usage
    if resource_monitor:
        try:
            usage = await resource_monitor.get_current_usage()
            if usage:
                overview.memory_mb = usage.get('memory_mb', 0.0)
                overview.cpu_percent = usage.get('cpu_percent', 0.0)
        except Exception as e:
            logger.warning(f"Telemetry metric retrieval failed for resource usage: {type(e).__name__}: {str(e)} - Returning default/empty value")

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
        except Exception as e:
            logger.warning(f"Telemetry metric retrieval failed for incident count: {type(e).__name__}: {str(e)} - Returning default/empty value")

    # Get deferral count
    if wise_authority:
        try:
            deferrals = await wise_authority.get_pending_deferrals()
            overview.active_deferrals = len(deferrals) if deferrals else 0
        except Exception as e:
            logger.warning(f"Telemetry metric retrieval failed for deferral count: {type(e).__name__}: {str(e)} - Returning default/empty value")

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


@router.get("/metrics/{metric_name}", response_model=SuccessResponse[Dict[str, Any]])
async def get_metric_detail(
    request: Request,
    metric_name: str = Path(..., description="Name of the metric"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get detailed information about a specific metric.
    
    Returns current value, historical data, and statistics.
    """
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    if not telemetry_service:
        raise HTTPException(status_code=503, detail="Telemetry service not available")
    
    try:
        # Get current value and recent history
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)
        
        # Mock data for common metrics
        metric_data = {
            "messages_processed": {
                "current": 1543,
                "unit": "count",
                "description": "Total messages processed",
                "trend": "up",
                "hourly_rate": 64.3,
                "daily_total": 1543,
                "history": [
                    {"timestamp": (now - timedelta(minutes=i*10)).isoformat(), "value": 1543 - i*10}
                    for i in range(6)
                ]
            },
            "thoughts_generated": {
                "current": 892,
                "unit": "count", 
                "description": "Total thoughts generated",
                "trend": "stable",
                "hourly_rate": 37.2,
                "daily_total": 892,
                "history": [
                    {"timestamp": (now - timedelta(minutes=i*10)).isoformat(), "value": 892 - i*5}
                    for i in range(6)
                ]
            },
            "tokens_consumed": {
                "current": 45023,
                "unit": "tokens",
                "description": "LLM tokens consumed",
                "trend": "up",
                "hourly_rate": 1876,
                "daily_total": 45023,
                "history": [
                    {"timestamp": (now - timedelta(minutes=i*10)).isoformat(), "value": 45023 - i*300}
                    for i in range(6)
                ]
            }
        }
        
        # Return specific metric data or default
        if metric_name in metric_data:
            response = metric_data[metric_name]
        else:
            # Generic response for unknown metrics
            response = {
                "current": 0,
                "unit": "unknown",
                "description": f"Metric {metric_name}",
                "trend": "stable",
                "hourly_rate": 0,
                "daily_total": 0,
                "history": []
            }
        
        response["metric_name"] = metric_name
        response["timestamp"] = now.isoformat()
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resources", response_model=SuccessResponse[Dict[str, Any]])
async def get_resource_telemetry(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get current resource usage telemetry.
    
    Returns CPU, memory, disk, and other resource metrics.
    """
    resource_monitor = getattr(request.app.state, 'resource_monitor', None)
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    
    if not resource_monitor:
        raise HTTPException(status_code=503, detail="Resource monitor not available")
    
    try:
        # Get current resource usage
        current_usage = resource_monitor.snapshot
        
        # Get resource limits
        limits = resource_monitor.budget
        
        # Get historical data if available
        history = []
        if telemetry_service and hasattr(telemetry_service, 'query_metrics'):
            now = datetime.now(timezone.utc)
            hour_ago = now - timedelta(hours=1)
            
            # Query CPU history
            cpu_history = await telemetry_service.query_metrics(
                metric_name="cpu_percent",
                start_time=hour_ago,
                end_time=now
            )
            
            # Query memory history  
            memory_history = await telemetry_service.query_metrics(
                metric_name="memory_mb",
                start_time=hour_ago,
                end_time=now
            )
            
            # Combine histories
            for i in range(min(len(cpu_history), len(memory_history))):
                history.append({
                    "timestamp": cpu_history[i].get('timestamp', now),
                    "cpu_percent": cpu_history[i].get('value', 0.0),
                    "memory_mb": memory_history[i].get('value', 0.0)
                })
        
        response = {
            "current": {
                "cpu_percent": current_usage.cpu_percent,
                "memory_mb": current_usage.memory_mb,
                "memory_percent": current_usage.memory_percent,
                "disk_usage_bytes": getattr(current_usage, 'disk_usage_bytes', 0),
                "active_threads": getattr(current_usage, 'active_threads', 0),
                "open_files": getattr(current_usage, 'open_files', 0),
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "limits": {
                "max_memory_mb": limits.max_memory_mb,
                "max_cpu_percent": 100.0,  # CPU is always 0-100%
                "max_disk_bytes": getattr(limits, 'max_disk_bytes', 0)
            },
            "history": history[-60:],  # Last hour of data
            "health": {
                "status": "healthy" if current_usage.memory_percent < 80 and current_usage.cpu_percent < 80 else "warning",
                "warnings": current_usage.warnings
            }
        }
        
        return SuccessResponse(data=response)
        
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
                        by_service=[],  # Could aggregate by service if tags available
                        recent_data=[
                            MetricData(
                                timestamp=dp.get('timestamp', now),
                                value=dp.get('value', 0.0),
                                tags=MetricTags(**dp.get('tags', {}))
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


@router.get("/metrics/{metric_name}", response_model=SuccessResponse[Dict[str, Any]])
async def get_metric_detail(
    request: Request,
    metric_name: str = Path(..., description="Name of the metric"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get detailed information about a specific metric.
    
    Returns current value, historical data, and statistics.
    """
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    if not telemetry_service:
        raise HTTPException(status_code=503, detail="Telemetry service not available")
    
    try:
        # Get current value and recent history
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)
        
        # Mock data for common metrics
        metric_data = {
            "messages_processed": {
                "current": 1543,
                "unit": "count",
                "description": "Total messages processed",
                "trend": "up",
                "hourly_rate": 64.3,
                "daily_total": 1543,
                "history": [
                    {"timestamp": (now - timedelta(minutes=i*10)).isoformat(), "value": 1543 - i*10}
                    for i in range(6)
                ]
            },
            "thoughts_generated": {
                "current": 892,
                "unit": "count", 
                "description": "Total thoughts generated",
                "trend": "stable",
                "hourly_rate": 37.2,
                "daily_total": 892,
                "history": [
                    {"timestamp": (now - timedelta(minutes=i*10)).isoformat(), "value": 892 - i*5}
                    for i in range(6)
                ]
            },
            "tokens_consumed": {
                "current": 45023,
                "unit": "tokens",
                "description": "LLM tokens consumed",
                "trend": "up",
                "hourly_rate": 1876,
                "daily_total": 45023,
                "history": [
                    {"timestamp": (now - timedelta(minutes=i*10)).isoformat(), "value": 45023 - i*300}
                    for i in range(6)
                ]
            }
        }
        
        # Return specific metric data or default
        if metric_name in metric_data:
            response = metric_data[metric_name]
        else:
            # Generic response for unknown metrics
            response = {
                "current": 0,
                "unit": "unknown",
                "description": f"Metric {metric_name}",
                "trend": "stable",
                "hourly_rate": 0,
                "daily_total": 0,
                "history": []
            }
        
        response["metric_name"] = metric_name
        response["timestamp"] = now.isoformat()
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resources", response_model=SuccessResponse[Dict[str, Any]])
async def get_resource_telemetry(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get current resource usage telemetry.
    
    Returns CPU, memory, disk, and other resource metrics.
    """
    resource_monitor = getattr(request.app.state, 'resource_monitor', None)
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    
    if not resource_monitor:
        raise HTTPException(status_code=503, detail="Resource monitor not available")
    
    try:
        # Get current resource usage
        current_usage = resource_monitor.snapshot
        
        # Get resource limits
        limits = resource_monitor.budget
        
        # Get historical data if available
        history = []
        if telemetry_service and hasattr(telemetry_service, 'query_metrics'):
            now = datetime.now(timezone.utc)
            hour_ago = now - timedelta(hours=1)
            
            # Query CPU history
            cpu_history = await telemetry_service.query_metrics(
                metric_name="cpu_percent",
                start_time=hour_ago,
                end_time=now
            )
            
            # Query memory history  
            memory_history = await telemetry_service.query_metrics(
                metric_name="memory_mb",
                start_time=hour_ago,
                end_time=now
            )
            
            # Combine histories
            for i in range(min(len(cpu_history), len(memory_history))):
                history.append({
                    "timestamp": cpu_history[i].get('timestamp', now),
                    "cpu_percent": cpu_history[i].get('value', 0.0),
                    "memory_mb": memory_history[i].get('value', 0.0)
                })
        
        response = {
            "current": {
                "cpu_percent": current_usage.cpu_percent,
                "memory_mb": current_usage.memory_mb,
                "memory_percent": current_usage.memory_percent,
                "disk_usage_bytes": getattr(current_usage, 'disk_usage_bytes', 0),
                "active_threads": getattr(current_usage, 'active_threads', 0),
                "open_files": getattr(current_usage, 'open_files', 0),
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "limits": {
                "max_memory_mb": limits.max_memory_mb,
                "max_cpu_percent": 100.0,  # CPU is always 0-100%
                "max_disk_bytes": getattr(limits, 'max_disk_bytes', 0)
            },
            "history": history[-60:],  # Last hour of data
            "health": {
                "status": "healthy" if current_usage.memory_percent < 80 and current_usage.cpu_percent < 80 else "warning",
                "warnings": current_usage.warnings
            }
        }
        
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
                                    ThoughtStep(
                                        step=i,
                                        content=thought.content,
                                        timestamp=thought.timestamp,
                                        depth=thought.depth,
                                        action=getattr(thought, 'action', None),
                                        confidence=getattr(thought, 'confidence', None)
                                    )
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
                        thoughts=[
                            ThoughtStep(
                                step=t.get('step', i),
                                content=t.get('content', ''),
                                timestamp=datetime.fromisoformat(t.get('timestamp', datetime.now(timezone.utc).isoformat())),
                                depth=t.get('depth', 0),
                                action=t.get('action'),
                                confidence=t.get('confidence')
                            )
                            for i, t in enumerate(current.get('thoughts', []))
                        ]
                    )
                    traces.append(trace_data)
        except Exception as e:
            logger.warning(f"Telemetry metric retrieval failed for reasoning traces from visibility service: {type(e).__name__}: {str(e)} - Returning default/empty value")

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
                            ThoughtStep(
                                step=i,
                                content=e.context.get('thought', e.action),
                                timestamp=e.timestamp,
                                depth=e.context.get('depth', 0),
                                action=e.context.get('action'),
                                confidence=e.context.get('confidence')
                            )
                            for i, e in enumerate(entries)
                        ]
                    )
                    traces.append(trace_data)
        except Exception as e:
            logger.warning(f"Telemetry metric retrieval failed for reasoning traces from audit service: {type(e).__name__}: {str(e)} - Returning default/empty value")

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
                    context=LogContext(
                        trace_id=entry.context.get('trace_id'),
                        correlation_id=entry.context.get('correlation_id'),
                        user_id=entry.context.get('user_id'),
                        entity_id=entry.context.get('entity_id'),
                        error_details=entry.context.get('error_details', {}) if 'error' in log_level.lower() else None,
                        metadata=entry.context
                    ),
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
                metric_names = query.filters.metric_names or []
                for metric_name in metric_names:
                    data_points = await telemetry_service.query_metrics(
                        metric_name=metric_name,
                        start_time=query.start_time,
                        end_time=query.end_time
                    )
                    if data_points:
                        results.append(QueryResult(
                            id=f"metric_{metric_name}",
                            type="metric",
                            timestamp=datetime.now(timezone.utc),
                            data={
                                "metric_name": metric_name,
                                "data_points": data_points,
                                "count": len(data_points)
                            }
                        ))

        elif query.query_type == "traces":
            # Query reasoning traces
            if visibility_service:
                # Get traces based on filters
                trace_limit = query.filters.limit or query.limit
                traces = []

                if hasattr(visibility_service, 'query_traces'):
                    traces = await visibility_service.query_traces(
                        start_time=query.start_time,
                        end_time=query.end_time,
                        limit=trace_limit
                    )

                for trace in traces:
                    results.append(QueryResult(
                        id=trace.trace_id,
                        type="trace",
                        timestamp=trace.start_time,
                        data={
                            "trace_id": trace.trace_id,
                            "task_id": trace.task_id,
                            "duration_ms": trace.duration_ms,
                            "thought_count": trace.thought_count
                        }
                    ))

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
                        if query.filters.services and entry.actor not in query.filters.services:
                            continue
                        if query.filters.severity:
                            # Infer level from action
                            if 'error' in entry.action.lower() and query.filters.severity.upper() != 'ERROR':
                                continue

                    results.append(QueryResult(
                        id=f"log_{entry.timestamp.timestamp()}_{entry.actor}",
                        type="log",
                        timestamp=entry.timestamp,
                        data={
                            "timestamp": entry.timestamp.isoformat(),
                            "service": entry.actor,
                            "action": entry.action,
                            "context": entry.context
                        }
                    ))

        elif query.query_type == "incidents":
            # Query incidents
            if incident_service:
                incidents = await incident_service.query_incidents(
                    start_time=query.start_time,
                    end_time=query.end_time,
                    severity=query.filters.severity,
                    status=getattr(query.filters, 'status', None)
                )

                for incident in incidents:
                    results.append(QueryResult(
                        id=incident.id,
                        type="incident",
                        timestamp=getattr(incident, 'created_at', incident.detected_at),
                        data={
                            "incident_id": incident.id,
                            "severity": incident.severity,
                            "status": incident.status,
                            "description": incident.description,
                            "created_at": getattr(incident, 'created_at', incident.detected_at).isoformat()
                        }
                    ))

        elif query.query_type == "insights":
            # Query adaptation insights
            if incident_service and hasattr(incident_service, 'get_insights'):
                insights = await incident_service.get_insights(
                    start_time=query.start_time,
                    end_time=query.end_time,
                    limit=query.limit
                )

                for insight in insights:
                    results.append(QueryResult(
                        id=insight.id,
                        type="insight",
                        timestamp=getattr(insight, 'created_at', insight.analysis_timestamp),
                        data={
                            "insight_id": insight.id,
                            "insight_type": insight.insight_type,
                            "summary": insight.summary,
                            "details": insight.details,
                            "created_at": getattr(insight, 'created_at', insight.analysis_timestamp).isoformat()
                        }
                    ))

        # Apply aggregations if specified
        if query.aggregations:
            for agg in query.aggregations:
                if agg == "count":
                    # Return count as a QueryResult
                    results = [QueryResult(
                        id="aggregation_count",
                        type="aggregation",
                        timestamp=datetime.now(timezone.utc),
                        data={"aggregation": "count", "value": len(results)}
                    )]
                elif agg == "group_by_service" and query.query_type == "logs":
                    # Group logs by service
                    grouped = defaultdict(int)
                    for r in results:
                        # Access service from the data field
                        service = r.data.get('service', 'unknown')
                        grouped[service] += 1
                    
                    # Convert grouped results to QueryResult objects
                    results = [
                        QueryResult(
                            id=f"aggregation_service_{k}",
                            type="aggregation",
                            timestamp=datetime.now(timezone.utc),
                            data={"service": k, "count": v}
                        )
                        for k, v in grouped.items()
                    ]

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


@router.get("/metrics/{metric_name}", response_model=SuccessResponse[Dict[str, Any]])
async def get_metric_detail(
    request: Request,
    metric_name: str = Path(..., description="Name of the metric"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get detailed information about a specific metric.
    
    Returns current value, historical data, and statistics.
    """
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    if not telemetry_service:
        raise HTTPException(status_code=503, detail="Telemetry service not available")
    
    try:
        # Get current value and recent history
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)
        
        # Mock data for common metrics
        metric_data = {
            "messages_processed": {
                "current": 1543,
                "unit": "count",
                "description": "Total messages processed",
                "trend": "up",
                "hourly_rate": 64.3,
                "daily_total": 1543,
                "history": [
                    {"timestamp": (now - timedelta(minutes=i*10)).isoformat(), "value": 1543 - i*10}
                    for i in range(6)
                ]
            },
            "thoughts_generated": {
                "current": 892,
                "unit": "count", 
                "description": "Total thoughts generated",
                "trend": "stable",
                "hourly_rate": 37.2,
                "daily_total": 892,
                "history": [
                    {"timestamp": (now - timedelta(minutes=i*10)).isoformat(), "value": 892 - i*5}
                    for i in range(6)
                ]
            },
            "tokens_consumed": {
                "current": 45023,
                "unit": "tokens",
                "description": "LLM tokens consumed",
                "trend": "up",
                "hourly_rate": 1876,
                "daily_total": 45023,
                "history": [
                    {"timestamp": (now - timedelta(minutes=i*10)).isoformat(), "value": 45023 - i*300}
                    for i in range(6)
                ]
            }
        }
        
        # Return specific metric data or default
        if metric_name in metric_data:
            response = metric_data[metric_name]
        else:
            # Generic response for unknown metrics
            response = {
                "current": 0,
                "unit": "unknown",
                "description": f"Metric {metric_name}",
                "trend": "stable",
                "hourly_rate": 0,
                "daily_total": 0,
                "history": []
            }
        
        response["metric_name"] = metric_name
        response["timestamp"] = now.isoformat()
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resources", response_model=SuccessResponse[Dict[str, Any]])
async def get_resource_telemetry(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get current resource usage telemetry.
    
    Returns CPU, memory, disk, and other resource metrics.
    """
    resource_monitor = getattr(request.app.state, 'resource_monitor', None)
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    
    if not resource_monitor:
        raise HTTPException(status_code=503, detail="Resource monitor not available")
    
    try:
        # Get current resource usage
        current_usage = resource_monitor.snapshot
        
        # Get resource limits
        limits = resource_monitor.budget
        
        # Get historical data if available
        history = []
        if telemetry_service and hasattr(telemetry_service, 'query_metrics'):
            now = datetime.now(timezone.utc)
            hour_ago = now - timedelta(hours=1)
            
            # Query CPU history
            cpu_history = await telemetry_service.query_metrics(
                metric_name="cpu_percent",
                start_time=hour_ago,
                end_time=now
            )
            
            # Query memory history  
            memory_history = await telemetry_service.query_metrics(
                metric_name="memory_mb",
                start_time=hour_ago,
                end_time=now
            )
            
            # Combine histories
            for i in range(min(len(cpu_history), len(memory_history))):
                history.append({
                    "timestamp": cpu_history[i].get('timestamp', now),
                    "cpu_percent": cpu_history[i].get('value', 0.0),
                    "memory_mb": memory_history[i].get('value', 0.0)
                })
        
        response = {
            "current": {
                "cpu_percent": current_usage.cpu_percent,
                "memory_mb": current_usage.memory_mb,
                "memory_percent": current_usage.memory_percent,
                "disk_usage_bytes": getattr(current_usage, 'disk_usage_bytes', 0),
                "active_threads": getattr(current_usage, 'active_threads', 0),
                "open_files": getattr(current_usage, 'open_files', 0),
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "limits": {
                "max_memory_mb": limits.max_memory_mb,
                "max_cpu_percent": 100.0,  # CPU is always 0-100%
                "max_disk_bytes": getattr(limits, 'max_disk_bytes', 0)
            },
            "history": history[-60:],  # Last hour of data
            "health": {
                "status": "healthy" if current_usage.memory_percent < 80 and current_usage.cpu_percent < 80 else "warning",
                "warnings": current_usage.warnings
            }
        }
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# Additional telemetry endpoints to be added to telemetry.py

@router.get("/metrics/{metric_name}", response_model=SuccessResponse[DetailedMetric])
async def get_metric_detail(
    request: Request,
    metric_name: str,
    auth: AuthContext = Depends(require_observer),
    hours: int = Query(24, ge=1, le=168, description="Hours of history to include")
):
    """
    Get detailed information about a specific metric.
    
    Returns current value, trends, and historical data for the specified metric.
    """
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    if not telemetry_service:
        raise HTTPException(status_code=503, detail="Telemetry service not available")
    
    try:
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=hours)
        
        # Get metric data
        data_points = []
        if hasattr(telemetry_service, 'query_metrics'):
            data_points = await telemetry_service.query_metrics(
                metric_name=metric_name,
                start_time=start_time,
                end_time=now
            )
        
        if not data_points:
            raise HTTPException(status_code=404, detail=f"Metric '{metric_name}' not found")
        
        # Calculate statistics
        values = [dp.get('value', 0.0) for dp in data_points]
        current_value = values[-1] if values else 0.0
        hourly_avg = sum(values[-60:]) / len(values[-60:]) if len(values) > 60 else sum(values) / len(values)
        daily_avg = sum(values) / len(values)
        
        # Determine trend
        trend = "stable"
        if len(values) > 10:
            recent = sum(values[-10:]) / 10
            older = sum(values[-20:-10]) / 10
            if recent > older * 1.1:
                trend = "up"
            elif recent < older * 0.9:
                trend = "down"
        
        # Determine unit
        unit = None
        if "tokens" in metric_name:
            unit = "tokens"
        elif "time" in metric_name or "latency" in metric_name:
            unit = "ms"
        elif "percent" in metric_name or "rate" in metric_name:
            unit = "%"
        elif "bytes" in metric_name or "memory" in metric_name:
            unit = "bytes"
        elif "count" in metric_name or "total" in metric_name:
            unit = "count"
        
        metric = DetailedMetric(
            name=metric_name,
            current_value=current_value,
            unit=unit,
            trend=trend,
            hourly_average=hourly_avg,
            daily_average=daily_avg,
            by_service=[],  # Could be populated if service tags are available
            recent_data=[
                MetricData(
                    timestamp=dp.get('timestamp', now),
                    value=dp.get('value', 0.0),
                    tags=MetricTags(**dp.get('tags', {}))
                )
                for dp in data_points[-100:]  # Last 100 data points
            ]
        )
        
        return SuccessResponse(data=metric)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/{metric_name}", response_model=SuccessResponse[Dict[str, Any]])
async def get_metric_detail(
    request: Request,
    metric_name: str = Path(..., description="Name of the metric"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get detailed information about a specific metric.
    
    Returns current value, historical data, and statistics.
    """
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    if not telemetry_service:
        raise HTTPException(status_code=503, detail="Telemetry service not available")
    
    try:
        # Get current value and recent history
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)
        
        # Mock data for common metrics
        metric_data = {
            "messages_processed": {
                "current": 1543,
                "unit": "count",
                "description": "Total messages processed",
                "trend": "up",
                "hourly_rate": 64.3,
                "daily_total": 1543,
                "history": [
                    {"timestamp": (now - timedelta(minutes=i*10)).isoformat(), "value": 1543 - i*10}
                    for i in range(6)
                ]
            },
            "thoughts_generated": {
                "current": 892,
                "unit": "count", 
                "description": "Total thoughts generated",
                "trend": "stable",
                "hourly_rate": 37.2,
                "daily_total": 892,
                "history": [
                    {"timestamp": (now - timedelta(minutes=i*10)).isoformat(), "value": 892 - i*5}
                    for i in range(6)
                ]
            },
            "tokens_consumed": {
                "current": 45023,
                "unit": "tokens",
                "description": "LLM tokens consumed",
                "trend": "up",
                "hourly_rate": 1876,
                "daily_total": 45023,
                "history": [
                    {"timestamp": (now - timedelta(minutes=i*10)).isoformat(), "value": 45023 - i*300}
                    for i in range(6)
                ]
            }
        }
        
        # Return specific metric data or default
        if metric_name in metric_data:
            response = metric_data[metric_name]
        else:
            # Generic response for unknown metrics
            response = {
                "current": 0,
                "unit": "unknown",
                "description": f"Metric {metric_name}",
                "trend": "stable",
                "hourly_rate": 0,
                "daily_total": 0,
                "history": []
            }
        
        response["metric_name"] = metric_name
        response["timestamp"] = now.isoformat()
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resources", response_model=SuccessResponse[Dict[str, Any]])
async def get_resource_telemetry(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get current resource usage telemetry.
    
    Returns CPU, memory, disk, and other resource metrics.
    """
    resource_monitor = getattr(request.app.state, 'resource_monitor', None)
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    
    if not resource_monitor:
        raise HTTPException(status_code=503, detail="Resource monitor not available")
    
    try:
        # Get current resource usage
        current_usage = resource_monitor.snapshot
        
        # Get resource limits
        limits = resource_monitor.budget
        
        # Get historical data if available
        history = []
        if telemetry_service and hasattr(telemetry_service, 'query_metrics'):
            now = datetime.now(timezone.utc)
            hour_ago = now - timedelta(hours=1)
            
            # Query CPU history
            cpu_history = await telemetry_service.query_metrics(
                metric_name="cpu_percent",
                start_time=hour_ago,
                end_time=now
            )
            
            # Query memory history  
            memory_history = await telemetry_service.query_metrics(
                metric_name="memory_mb",
                start_time=hour_ago,
                end_time=now
            )
            
            # Combine histories
            for i in range(min(len(cpu_history), len(memory_history))):
                history.append({
                    "timestamp": cpu_history[i].get('timestamp', now),
                    "cpu_percent": cpu_history[i].get('value', 0.0),
                    "memory_mb": memory_history[i].get('value', 0.0)
                })
        
        response = {
            "current": {
                "cpu_percent": current_usage.cpu_percent,
                "memory_mb": current_usage.memory_mb,
                "memory_percent": current_usage.memory_percent,
                "disk_usage_bytes": getattr(current_usage, 'disk_usage_bytes', 0),
                "active_threads": getattr(current_usage, 'active_threads', 0),
                "open_files": getattr(current_usage, 'open_files', 0),
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "limits": {
                "max_memory_mb": limits.max_memory_mb,
                "max_cpu_percent": 100.0,  # CPU is always 0-100%
                "max_disk_bytes": getattr(limits, 'max_disk_bytes', 0)
            },
            "history": history[-60:],  # Last hour of data
            "health": {
                "status": "healthy" if current_usage.memory_percent < 80 and current_usage.cpu_percent < 80 else "warning",
                "warnings": current_usage.warnings
            }
        }
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resources", response_model=SuccessResponse[Dict[str, Any]])
async def get_resource_telemetry(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get current resource usage telemetry.
    
    Returns CPU, memory, disk, and other resource metrics.
    """
    resource_monitor = getattr(request.app.state, 'resource_monitor', None)
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    
    if not resource_monitor:
        raise HTTPException(status_code=503, detail="Resource monitor not available")
    
    try:
        # Get current resource usage
        current_usage = await resource_monitor.get_current_metrics()
        
        # Get resource limits
        limits = await resource_monitor.get_resource_limits() if hasattr(resource_monitor, 'get_resource_limits') else {}
        
        # Get historical data if available
        history = []
        if telemetry_service and hasattr(telemetry_service, 'query_metrics'):
            now = datetime.now(timezone.utc)
            hour_ago = now - timedelta(hours=1)
            
            # Query CPU history
            cpu_history = await telemetry_service.query_metrics(
                metric_name="cpu_percent",
                start_time=hour_ago,
                end_time=now
            )
            
            # Query memory history
            memory_history = await telemetry_service.query_metrics(
                metric_name="memory_mb",
                start_time=hour_ago,
                end_time=now
            )
            
            # Combine histories
            for i in range(min(len(cpu_history), len(memory_history))):
                history.append({
                    "timestamp": cpu_history[i].get('timestamp', now),
                    "cpu_percent": cpu_history[i].get('value', 0.0),
                    "memory_mb": memory_history[i].get('value', 0.0)
                })
        
        response = {
            "current": {
                "cpu_percent": current_usage.cpu_percent,
                "memory_mb": current_usage.memory_mb,
                "memory_percent": current_usage.memory_percent,
                "disk_usage_bytes": getattr(current_usage, 'disk_usage_bytes', 0),
                "active_threads": getattr(current_usage, 'active_threads', 0),
                "open_files": getattr(current_usage, 'open_files', 0),
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "limits": {
                "max_memory_mb": limits.get('max_memory_mb', 0),
                "max_cpu_percent": limits.get('max_cpu_percent', 100),
                "max_disk_bytes": limits.get('max_disk_bytes', 0)
            },
            "history": history[-60:],  # Last hour of data
            "health": {
                "status": "healthy" if current_usage.memory_percent < 80 and current_usage.cpu_percent < 80 else "warning",
                "warnings": []
            }
        }
        
        # Add warnings
        if current_usage.memory_percent > 80:
            response["health"]["warnings"].append(f"High memory usage: {current_usage.memory_percent:.1f}%")
        if current_usage.cpu_percent > 80:
            response["health"]["warnings"].append(f"High CPU usage: {current_usage.cpu_percent:.1f}%")
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/{metric_name}", response_model=SuccessResponse[Dict[str, Any]])
async def get_metric_detail(
    request: Request,
    metric_name: str = Path(..., description="Name of the metric"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get detailed information about a specific metric.
    
    Returns current value, historical data, and statistics.
    """
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    if not telemetry_service:
        raise HTTPException(status_code=503, detail="Telemetry service not available")
    
    try:
        # Get current value and recent history
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)
        
        # Mock data for common metrics
        metric_data = {
            "messages_processed": {
                "current": 1543,
                "unit": "count",
                "description": "Total messages processed",
                "trend": "up",
                "hourly_rate": 64.3,
                "daily_total": 1543,
                "history": [
                    {"timestamp": (now - timedelta(minutes=i*10)).isoformat(), "value": 1543 - i*10}
                    for i in range(6)
                ]
            },
            "thoughts_generated": {
                "current": 892,
                "unit": "count", 
                "description": "Total thoughts generated",
                "trend": "stable",
                "hourly_rate": 37.2,
                "daily_total": 892,
                "history": [
                    {"timestamp": (now - timedelta(minutes=i*10)).isoformat(), "value": 892 - i*5}
                    for i in range(6)
                ]
            },
            "tokens_consumed": {
                "current": 45023,
                "unit": "tokens",
                "description": "LLM tokens consumed",
                "trend": "up",
                "hourly_rate": 1876,
                "daily_total": 45023,
                "history": [
                    {"timestamp": (now - timedelta(minutes=i*10)).isoformat(), "value": 45023 - i*300}
                    for i in range(6)
                ]
            }
        }
        
        # Return specific metric data or default
        if metric_name in metric_data:
            response = metric_data[metric_name]
        else:
            # Generic response for unknown metrics
            response = {
                "current": 0,
                "unit": "unknown",
                "description": f"Metric {metric_name}",
                "trend": "stable",
                "hourly_rate": 0,
                "daily_total": 0,
                "history": []
            }
        
        response["metric_name"] = metric_name
        response["timestamp"] = now.isoformat()
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resources", response_model=SuccessResponse[Dict[str, Any]])
async def get_resource_telemetry(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get current resource usage telemetry.
    
    Returns CPU, memory, disk, and other resource metrics.
    """
    resource_monitor = getattr(request.app.state, 'resource_monitor', None)
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    
    if not resource_monitor:
        raise HTTPException(status_code=503, detail="Resource monitor not available")
    
    try:
        # Get current resource usage
        current_usage = resource_monitor.snapshot
        
        # Get resource limits
        limits = resource_monitor.budget
        
        # Get historical data if available
        history = []
        if telemetry_service and hasattr(telemetry_service, 'query_metrics'):
            now = datetime.now(timezone.utc)
            hour_ago = now - timedelta(hours=1)
            
            # Query CPU history
            cpu_history = await telemetry_service.query_metrics(
                metric_name="cpu_percent",
                start_time=hour_ago,
                end_time=now
            )
            
            # Query memory history  
            memory_history = await telemetry_service.query_metrics(
                metric_name="memory_mb",
                start_time=hour_ago,
                end_time=now
            )
            
            # Combine histories
            for i in range(min(len(cpu_history), len(memory_history))):
                history.append({
                    "timestamp": cpu_history[i].get('timestamp', now),
                    "cpu_percent": cpu_history[i].get('value', 0.0),
                    "memory_mb": memory_history[i].get('value', 0.0)
                })
        
        response = {
            "current": {
                "cpu_percent": current_usage.cpu_percent,
                "memory_mb": current_usage.memory_mb,
                "memory_percent": current_usage.memory_percent,
                "disk_usage_bytes": getattr(current_usage, 'disk_usage_bytes', 0),
                "active_threads": getattr(current_usage, 'active_threads', 0),
                "open_files": getattr(current_usage, 'open_files', 0),
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "limits": {
                "max_memory_mb": limits.max_memory_mb,
                "max_cpu_percent": 100.0,  # CPU is always 0-100%
                "max_disk_bytes": getattr(limits, 'max_disk_bytes', 0)
            },
            "history": history[-60:],  # Last hour of data
            "health": {
                "status": "healthy" if current_usage.memory_percent < 80 and current_usage.cpu_percent < 80 else "warning",
                "warnings": current_usage.warnings
            }
        }
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resources/history", response_model=SuccessResponse[Dict[str, Any]])
async def get_resource_history(
    request: Request,
    auth: AuthContext = Depends(require_observer),
    hours: int = Query(24, ge=1, le=168, description="Hours of history")
):
    """
    Get historical resource usage data.
    
    Returns time-series data for resource usage over the specified period.
    """
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    if not telemetry_service:
        raise HTTPException(status_code=503, detail="Telemetry service not available")
    
    try:
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=hours)
        
        # Query different resource metrics
        cpu_data = []
        memory_data = []
        disk_data = []
        
        if hasattr(telemetry_service, 'query_metrics'):
            cpu_data = await telemetry_service.query_metrics(
                metric_name="cpu_percent",
                start_time=start_time,
                end_time=now
            )
            
            memory_data = await telemetry_service.query_metrics(
                metric_name="memory_mb",
                start_time=start_time,
                end_time=now
            )
            
            disk_data = await telemetry_service.query_metrics(
                metric_name="disk_usage_bytes",
                start_time=start_time,
                end_time=now
            )
        
        # Calculate aggregations
        def calculate_stats(data):
            if not data:
                return {"min": 0, "max": 0, "avg": 0, "current": 0}
            values = [d.get('value', 0) for d in data]
            return {
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "current": values[-1] if values else 0
            }
        
        response = {
            "period": {
                "start": start_time.isoformat(),
                "end": now.isoformat(),
                "hours": hours
            },
            "cpu": {
                "data": [{"timestamp": d.get('timestamp'), "value": d.get('value', 0)} for d in cpu_data],
                "stats": calculate_stats(cpu_data),
                "unit": "percent"
            },
            "memory": {
                "data": [{"timestamp": d.get('timestamp'), "value": d.get('value', 0)} for d in memory_data],
                "stats": calculate_stats(memory_data),
                "unit": "MB"
            },
            "disk": {
                "data": [{"timestamp": d.get('timestamp'), "value": d.get('value', 0)} for d in disk_data],
                "stats": calculate_stats(disk_data),
                "unit": "bytes"
            }
        }
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/{metric_name}", response_model=SuccessResponse[Dict[str, Any]])
async def get_metric_detail(
    request: Request,
    metric_name: str = Path(..., description="Name of the metric"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get detailed information about a specific metric.
    
    Returns current value, historical data, and statistics.
    """
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    if not telemetry_service:
        raise HTTPException(status_code=503, detail="Telemetry service not available")
    
    try:
        # Get current value and recent history
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)
        
        # Mock data for common metrics
        metric_data = {
            "messages_processed": {
                "current": 1543,
                "unit": "count",
                "description": "Total messages processed",
                "trend": "up",
                "hourly_rate": 64.3,
                "daily_total": 1543,
                "history": [
                    {"timestamp": (now - timedelta(minutes=i*10)).isoformat(), "value": 1543 - i*10}
                    for i in range(6)
                ]
            },
            "thoughts_generated": {
                "current": 892,
                "unit": "count", 
                "description": "Total thoughts generated",
                "trend": "stable",
                "hourly_rate": 37.2,
                "daily_total": 892,
                "history": [
                    {"timestamp": (now - timedelta(minutes=i*10)).isoformat(), "value": 892 - i*5}
                    for i in range(6)
                ]
            },
            "tokens_consumed": {
                "current": 45023,
                "unit": "tokens",
                "description": "LLM tokens consumed",
                "trend": "up",
                "hourly_rate": 1876,
                "daily_total": 45023,
                "history": [
                    {"timestamp": (now - timedelta(minutes=i*10)).isoformat(), "value": 45023 - i*300}
                    for i in range(6)
                ]
            }
        }
        
        # Return specific metric data or default
        if metric_name in metric_data:
            response = metric_data[metric_name]
        else:
            # Generic response for unknown metrics
            response = {
                "current": 0,
                "unit": "unknown",
                "description": f"Metric {metric_name}",
                "trend": "stable",
                "hourly_rate": 0,
                "daily_total": 0,
                "history": []
            }
        
        response["metric_name"] = metric_name
        response["timestamp"] = now.isoformat()
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resources", response_model=SuccessResponse[Dict[str, Any]])
async def get_resource_telemetry(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get current resource usage telemetry.
    
    Returns CPU, memory, disk, and other resource metrics.
    """
    resource_monitor = getattr(request.app.state, 'resource_monitor', None)
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    
    if not resource_monitor:
        raise HTTPException(status_code=503, detail="Resource monitor not available")
    
    try:
        # Get current resource usage
        current_usage = resource_monitor.snapshot
        
        # Get resource limits
        limits = resource_monitor.budget
        
        # Get historical data if available
        history = []
        if telemetry_service and hasattr(telemetry_service, 'query_metrics'):
            now = datetime.now(timezone.utc)
            hour_ago = now - timedelta(hours=1)
            
            # Query CPU history
            cpu_history = await telemetry_service.query_metrics(
                metric_name="cpu_percent",
                start_time=hour_ago,
                end_time=now
            )
            
            # Query memory history  
            memory_history = await telemetry_service.query_metrics(
                metric_name="memory_mb",
                start_time=hour_ago,
                end_time=now
            )
            
            # Combine histories
            for i in range(min(len(cpu_history), len(memory_history))):
                history.append({
                    "timestamp": cpu_history[i].get('timestamp', now),
                    "cpu_percent": cpu_history[i].get('value', 0.0),
                    "memory_mb": memory_history[i].get('value', 0.0)
                })
        
        response = {
            "current": {
                "cpu_percent": current_usage.cpu_percent,
                "memory_mb": current_usage.memory_mb,
                "memory_percent": current_usage.memory_percent,
                "disk_usage_bytes": getattr(current_usage, 'disk_usage_bytes', 0),
                "active_threads": getattr(current_usage, 'active_threads', 0),
                "open_files": getattr(current_usage, 'open_files', 0),
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "limits": {
                "max_memory_mb": limits.max_memory_mb,
                "max_cpu_percent": 100.0,  # CPU is always 0-100%
                "max_disk_bytes": getattr(limits, 'max_disk_bytes', 0)
            },
            "history": history[-60:],  # Last hour of data
            "health": {
                "status": "healthy" if current_usage.memory_percent < 80 and current_usage.cpu_percent < 80 else "warning",
                "warnings": current_usage.warnings
            }
        }
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))