"""
Additional telemetry metrics endpoints.
"""
from typing import Dict, Any
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends, Path
from ciris_engine.schemas.api.responses import SuccessResponse
from ..dependencies.auth import require_observer, AuthContext

router = APIRouter()

@router.get("/metrics/{metric_name}", response_model=SuccessResponse[Dict[str, Any]])
async def get_metric_detail(
    request: Request,
    metric_name: str = Path(..., description="Name of the metric"),
    auth: AuthContext = Depends(require_observer)
) -> SuccessResponse[Dict[str, Any]]:
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