"""
Telemetry service endpoints for CIRIS API v1.

Rich telemetry data from graph-based TSDB.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends, Query, WebSocket
from pydantic import BaseModel, Field

from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.schemas.runtime.system_context import TelemetrySummary
from ciris_engine.api.dependencies.auth import require_observer, require_admin, AuthContext

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

# Request/Response schemas

class MetricData(BaseModel):
    """Single metric data point."""
    timestamp: datetime = Field(..., description="When metric was recorded")
    value: float = Field(..., description="Metric value")
    tags: Dict[str, str] = Field(default_factory=dict, description="Metric tags")

class MetricSeries(BaseModel):
    """Time series data for a metric."""
    metric_name: str = Field(..., description="Name of the metric")
    data_points: List[MetricData] = Field(..., description="Time series data")
    unit: Optional[str] = Field(None, description="Metric unit")
    description: Optional[str] = Field(None, description="Metric description")

class MetricsResponse(BaseModel):
    """Current metrics response."""
    metrics: Dict[str, MetricSeries] = Field(..., description="Current metrics by name")
    timestamp: datetime = Field(..., description="Response timestamp")

class ResourceUsageAPI(BaseModel):
    """Resource usage information for API."""
    current_tokens: int = Field(0, description="Tokens used today")
    hourly_token_rate: float = Field(0.0, description="Average tokens per hour")
    daily_token_limit: int = Field(1000000, description="Daily token limit")
    cost_usd_cents: float = Field(0.0, description="Cost in US cents")
    carbon_grams: float = Field(0.0, description="Carbon footprint in grams")
    memory_mb: float = Field(0.0, description="Memory usage in MB")
    cpu_percent: float = Field(0.0, description="CPU usage percentage")
    disk_mb: float = Field(0.0, description="Disk usage in MB")
    active_handlers: int = Field(0, description="Active handler count")
    pending_tasks: int = Field(0, description="Pending task count")
    queue_depth: int = Field(0, description="Message queue depth")

class ResourceHistory(BaseModel):
    """Historical resource usage."""
    time_buckets: List[Dict[str, Any]] = Field(..., description="Resource usage over time")
    start_time: datetime = Field(..., description="Start of history")
    end_time: datetime = Field(..., description="End of history")
    bucket_size_minutes: int = Field(..., description="Size of each time bucket")

class TelemetryQuery(BaseModel):
    """Custom telemetry query."""
    metric_names: List[str] = Field(..., description="Metrics to query")
    start_time: Optional[datetime] = Field(None, description="Query start time")
    end_time: Optional[datetime] = Field(None, description="Query end time")
    tags: Optional[Dict[str, str]] = Field(None, description="Filter by tags")
    aggregation: Optional[str] = Field(None, description="Aggregation method")

# Endpoints

@router.get("/overview", response_model=SuccessResponse[TelemetrySummary])
async def get_telemetry_overview(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    System telemetry summary.
    
    Get comprehensive overview of system metrics and activity.
    """
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    if not telemetry_service:
        raise HTTPException(status_code=503, detail="Telemetry service not available")
    
    try:
        # Get telemetry summary
        if hasattr(telemetry_service, 'get_telemetry_summary'):
            summary = await telemetry_service.get_telemetry_summary()
            return SuccessResponse(data=summary)
        else:
            # Fallback: build summary from available data
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(hours=24)
            
            summary = TelemetrySummary(
                window_start=window_start,
                window_end=now,
                uptime_seconds=0.0,  # Would get from time service
                messages_processed_24h=0,
                thoughts_processed_24h=0,
                tasks_completed_24h=0,
                errors_24h=0,
                messages_current_hour=0,
                thoughts_current_hour=0,
                errors_current_hour=0,
                service_calls={},
                service_errors={},
                service_latency_ms={},
                tokens_per_hour=0.0,
                cost_per_hour_cents=0.0,
                carbon_per_hour_grams=0.0,
                error_rate_percent=0.0,
                avg_thought_depth=0.0,
                queue_saturation=0.0
            )
            
            return SuccessResponse(data=summary)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics", response_model=SuccessResponse[MetricsResponse])
async def get_current_metrics(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Current metrics.
    
    Get current values for all tracked metrics.
    """
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    if not telemetry_service:
        raise HTTPException(status_code=503, detail="Telemetry service not available")
    
    try:
        # Get all current metrics
        metrics_dict = {}
        
        # Common metrics to query
        metric_names = [
            "messages_processed",
            "thoughts_processed",
            "tasks_completed",
            "errors",
            "tokens_consumed",
            "api_requests",
            "memory_operations"
        ]
        
        for metric_name in metric_names:
            if hasattr(telemetry_service, 'query_metrics'):
                # Get last hour of data
                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(hours=1)
                
                data_points = await telemetry_service.query_metrics(
                    metric_name=metric_name,
                    start_time=start_time,
                    end_time=end_time
                )
                
                if data_points:
                    metric_series = MetricSeries(
                        metric_name=metric_name,
                        data_points=[
                            MetricData(
                                timestamp=dp.get('timestamp', datetime.now(timezone.utc)),
                                value=dp.get('value', 0.0),
                                tags=dp.get('tags', {})
                            )
                            for dp in data_points
                        ]
                    )
                    metrics_dict[metric_name] = metric_series
        
        response = MetricsResponse(
            metrics=metrics_dict,
            timestamp=datetime.now(timezone.utc)
        )
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics/{metric_name}", response_model=SuccessResponse[MetricSeries])
async def get_metric_details(
    request: Request,
    metric_name: str,
    hours: int = Query(24, ge=1, le=168, description="Hours of history"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Specific metric history.
    
    Get detailed history for a specific metric.
    """
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    if not telemetry_service:
        raise HTTPException(status_code=503, detail="Telemetry service not available")
    
    try:
        # Query metric history
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)
        
        data_points = await telemetry_service.query_metrics(
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time
        )
        
        if not data_points:
            raise HTTPException(
                status_code=404,
                detail=f"Metric '{metric_name}' not found"
            )
        
        metric_series = MetricSeries(
            metric_name=metric_name,
            data_points=[
                MetricData(
                    timestamp=dp.get('timestamp', datetime.now(timezone.utc)),
                    value=dp.get('value', 0.0),
                    tags=dp.get('tags', {})
                )
                for dp in data_points
            ]
        )
        
        return SuccessResponse(data=metric_series)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/resources", response_model=SuccessResponse[ResourceUsageAPI])
async def get_resource_usage(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Resource usage.
    
    Get current system resource consumption.
    """
    # Try to get from telemetry summary first
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    if telemetry_service and hasattr(telemetry_service, 'get_telemetry_summary'):
        try:
            summary = await telemetry_service.get_telemetry_summary()
            
            # Extract resource usage from summary
            usage = ResourceUsageAPI(
                current_tokens=0,  # Would track in service
                hourly_token_rate=summary.tokens_per_hour,
                daily_token_limit=1000000,  # From config
                cost_usd_cents=summary.cost_per_hour_cents,
                carbon_grams=summary.carbon_per_hour_grams,
                memory_mb=0.0,  # Would get from resource monitor
                cpu_percent=0.0,
                disk_mb=0.0,
                active_handlers=0,
                pending_tasks=0,
                queue_depth=0
            )
            
            return SuccessResponse(data=usage)
        except:
            pass
    
    # Fallback to empty usage
    usage = ResourceUsageAPI(
        current_tokens=0,
        hourly_token_rate=0.0,
        daily_token_limit=1000000,
        cost_usd_cents=0.0,
        carbon_grams=0.0,
        memory_mb=0.0,
        cpu_percent=0.0,
        disk_mb=0.0,
        active_handlers=0,
        pending_tasks=0,
        queue_depth=0
    )
    
    return SuccessResponse(data=usage)

@router.get("/resources/history", response_model=SuccessResponse[ResourceHistory])
async def get_resource_history(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="Hours of history"),
    bucket_minutes: int = Query(60, ge=5, le=1440, description="Bucket size"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Historical resource usage.
    
    Get resource consumption over time.
    """
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    if not telemetry_service:
        raise HTTPException(status_code=503, detail="Telemetry service not available")
    
    try:
        # Query resource metrics
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)
        
        # Get token usage history
        token_history = []
        if hasattr(telemetry_service, 'query_metrics'):
            token_data = await telemetry_service.query_metrics(
                metric_name="tokens_consumed",
                start_time=start_time,
                end_time=end_time
            )
            
            # Aggregate into buckets
            # This is a simplified bucketing - real implementation would be more sophisticated
            buckets = []
            current_bucket_start = start_time
            
            while current_bucket_start < end_time:
                bucket_end = current_bucket_start + timedelta(minutes=bucket_minutes)
                
                # Sum values in this bucket
                bucket_sum = 0.0
                bucket_count = 0
                
                for dp in token_data:
                    dp_time = dp.get('timestamp')
                    if dp_time and current_bucket_start <= dp_time < bucket_end:
                        bucket_sum += dp.get('value', 0.0)
                        bucket_count += 1
                
                buckets.append({
                    "start_time": current_bucket_start,
                    "end_time": bucket_end,
                    "tokens": bucket_sum,
                    "cost_cents": bucket_sum * 0.0001,  # Example cost calculation
                    "carbon_grams": bucket_sum * 0.00001  # Example carbon calculation
                })
                
                current_bucket_start = bucket_end
            
            token_history = buckets
        
        history = ResourceHistory(
            time_buckets=token_history,
            start_time=start_time,
            end_time=end_time,
            bucket_size_minutes=bucket_minutes
        )
        
        return SuccessResponse(data=history)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/query", response_model=SuccessResponse[Dict[str, MetricSeries]])
async def query_telemetry(
    request: Request,
    query: TelemetryQuery,
    auth: AuthContext = Depends(require_admin)
):
    """
    Custom telemetry queries.
    
    Execute custom queries against telemetry data.
    Requires ADMIN role.
    """
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    if not telemetry_service:
        raise HTTPException(status_code=503, detail="Telemetry service not available")
    
    try:
        results = {}
        
        for metric_name in query.metric_names:
            data_points = await telemetry_service.query_metrics(
                metric_name=metric_name,
                start_time=query.start_time,
                end_time=query.end_time,
                tags=query.tags
            )
            
            if data_points:
                results[metric_name] = MetricSeries(
                    metric_name=metric_name,
                    data_points=[
                        MetricData(
                            timestamp=dp.get('timestamp', datetime.now(timezone.utc)),
                            value=dp.get('value', 0.0),
                            tags=dp.get('tags', {})
                        )
                        for dp in data_points
                    ]
                )
        
        return SuccessResponse(data=results)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/stream")
async def telemetry_stream(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="API key for authentication")
):
    """
    Real-time metric stream.
    
    Stream telemetry updates via WebSocket.
    """
    # Validate authentication
    if token:
        auth_service = getattr(websocket.app.state, 'auth_service', None)
        if auth_service:
            key_info = await auth_service.validate_api_key(token)
            if not key_info:
                await websocket.close(code=1008, reason="Invalid authentication")
                return
    
    await websocket.accept()
    
    try:
        # TODO: Implement real-time telemetry streaming
        # This would subscribe to telemetry updates and forward them
        while True:
            # Placeholder - would stream actual metrics
            await asyncio.sleep(5)
            await websocket.send_json({
                "type": "metric",
                "metric_name": "heartbeat",
                "value": 1.0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close(code=1011, reason="Internal error")

import asyncio
import logging
logger = logging.getLogger(__name__)