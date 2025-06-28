"""
Resource Monitor Service endpoints for CIRIS API v1.

Monitors system resource usage and limits. Includes predictive analytics.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends, Body
from pydantic import BaseModel, Field, field_serializer
import logging

from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.schemas.services.resources_core import (
    ResourceBudget,
    ResourceSnapshot,
    ResourceAlert,
    ResourceLimit,
    ResourceAction
)
from ciris_engine.api.dependencies.auth import require_observer, require_admin, AuthContext

router = APIRouter(prefix="/resources", tags=["resources"])
logger = logging.getLogger(__name__)

# Request/Response schemas

class ResourceLimitsResponse(BaseModel):
    """Resource limits configuration."""
    memory_mb: ResourceLimit = Field(..., description="Memory usage limits in MB")
    cpu_percent: ResourceLimit = Field(..., description="CPU usage limits in percent")
    tokens_hour: ResourceLimit = Field(..., description="Token usage per hour")
    tokens_day: ResourceLimit = Field(..., description="Token usage per day")
    disk_mb: ResourceLimit = Field(..., description="Disk usage limits in MB")
    thoughts_active: ResourceLimit = Field(..., description="Active thoughts limit")
    effective_from: datetime = Field(..., description="When these limits became effective")
    
    @field_serializer('effective_from')
    def serialize_effective_from(self, effective_from: datetime, _info):
        return effective_from.isoformat() if effective_from else None

class ResourceUsageResponse(BaseModel):
    """Current resource usage snapshot."""
    snapshot: ResourceSnapshot = Field(..., description="Current resource usage")
    budget: ResourceBudget = Field(..., description="Configured resource budget")
    timestamp: datetime = Field(..., description="When snapshot was taken")
    
    @field_serializer('timestamp')
    def serialize_timestamp(self, timestamp: datetime, _info):
        return timestamp.isoformat() if timestamp else None
    
class ResourcePrediction(BaseModel):
    """Resource usage prediction."""
    resource_name: str = Field(..., description="Name of the resource")
    current_usage: float = Field(..., description="Current usage value")
    predicted_usage_1h: float = Field(..., description="Predicted usage in 1 hour")
    predicted_usage_24h: float = Field(..., description="Predicted usage in 24 hours")
    time_to_limit: Optional[float] = Field(None, description="Hours until limit reached (null if never)")
    confidence: float = Field(..., ge=0, le=1, description="Prediction confidence (0-1)")
    trend: str = Field(..., description="Usage trend (increasing, stable, decreasing)")

class ResourcePredictionsResponse(BaseModel):
    """Resource usage predictions."""
    predictions: List[ResourcePrediction] = Field(..., description="Predictions for each resource")
    analysis_window_hours: int = Field(..., description="Hours of history analyzed")
    generated_at: datetime = Field(..., description="When predictions were generated")
    
    @field_serializer('generated_at')
    def serialize_generated_at(self, generated_at: datetime, _info):
        return generated_at.isoformat() if generated_at else None

class AlertConfiguration(BaseModel):
    """Alert configuration update request."""
    resource_name: str = Field(..., description="Resource to configure (memory_mb, cpu_percent, etc.)")
    warning_threshold: Optional[int] = Field(None, description="Warning threshold value")
    critical_threshold: Optional[int] = Field(None, description="Critical threshold value")
    action: Optional[ResourceAction] = Field(None, description="Action when limit exceeded")
    cooldown_seconds: Optional[int] = Field(None, ge=0, description="Cooldown period in seconds")

class AlertConfigurationResponse(BaseModel):
    """Alert configuration response."""
    updated: bool = Field(..., description="Whether configuration was updated")
    resource_name: str = Field(..., description="Resource that was configured")
    new_config: ResourceLimit = Field(..., description="New configuration")
    previous_config: ResourceLimit = Field(..., description="Previous configuration")

# Endpoints

@router.get("/limits", response_model=SuccessResponse[ResourceLimitsResponse])
async def get_resource_limits(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Resource limits.
    
    Get configured resource usage limits and thresholds.
    """
    resource_monitor = getattr(request.app.state, 'resource_monitor', None)
    if not resource_monitor:
        raise HTTPException(status_code=503, detail="Resource monitor service not available")
    
    try:
        # Get current budget configuration
        budget = resource_monitor.budget
        
        response = ResourceLimitsResponse(
            memory_mb=budget.memory_mb,
            cpu_percent=budget.cpu_percent,
            tokens_hour=budget.tokens_hour,
            tokens_day=budget.tokens_day,
            disk_mb=budget.disk_mb,
            thoughts_active=budget.thoughts_active,
            effective_from=datetime.now(timezone.utc)  # Would track actual config time
        )
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        logger.error(f"Error getting resource limits: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/usage", response_model=SuccessResponse[ResourceUsageResponse])
async def get_resource_usage(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Current usage.
    
    Get current resource consumption and health status.
    """
    resource_monitor = getattr(request.app.state, 'resource_monitor', None)
    if not resource_monitor:
        raise HTTPException(status_code=503, detail="Resource monitor service not available")
    
    try:
        # Get current snapshot and budget
        snapshot = resource_monitor.snapshot
        budget = resource_monitor.budget
        
        response = ResourceUsageResponse(
            snapshot=snapshot,
            budget=budget,
            timestamp=datetime.now(timezone.utc)
        )
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        logger.error(f"Error getting resource usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/alerts", response_model=SuccessResponse[List[ResourceAlert]])
async def get_resource_alerts(
    request: Request,
    hours: int = 24,
    auth: AuthContext = Depends(require_observer)
):
    """
    Resource alerts.
    
    Get recent resource usage alerts and violations.
    """
    resource_monitor = getattr(request.app.state, 'resource_monitor', None)
    if not resource_monitor:
        raise HTTPException(status_code=503, detail="Resource monitor service not available")
    
    try:
        # In a real implementation, alerts would be stored and retrieved
        # For now, we'll generate alerts based on current state
        alerts = []
        snapshot = resource_monitor.snapshot
        budget = resource_monitor.budget
        now = datetime.now(timezone.utc)
        
        # Check each resource for current alerts
        resources_to_check = [
            ("memory_mb", snapshot.memory_mb, budget.memory_mb),
            ("cpu_percent", snapshot.cpu_percent, budget.cpu_percent),
            ("tokens_hour", snapshot.tokens_used_hour, budget.tokens_hour),
            ("tokens_day", snapshot.tokens_used_day, budget.tokens_day),
            ("thoughts_active", snapshot.thoughts_active, budget.thoughts_active)
        ]
        
        for resource_name, current_value, limit_config in resources_to_check:
            if current_value >= limit_config.critical:
                alert = ResourceAlert(
                    resource_type=resource_name,
                    current_value=float(current_value),
                    limit_value=float(limit_config.critical),
                    severity="critical",
                    action_taken=limit_config.action,
                    timestamp=now,
                    message=f"{resource_name} at critical level: {current_value}/{limit_config.limit}"
                )
                alerts.append(alert)
            elif current_value >= limit_config.warning:
                alert = ResourceAlert(
                    resource_type=resource_name,
                    current_value=float(current_value),
                    limit_value=float(limit_config.warning),
                    severity="warning",
                    action_taken=ResourceAction.LOG,
                    timestamp=now,
                    message=f"{resource_name} at warning level: {current_value}/{limit_config.limit}"
                )
                alerts.append(alert)
        
        # Add any warnings and critical messages from snapshot
        for warning in snapshot.warnings:
            parts = warning.split(":")
            if len(parts) == 2:
                resource_type = parts[0].strip()
                alert = ResourceAlert(
                    resource_type=resource_type,
                    current_value=0.0,  # Would parse from message
                    limit_value=0.0,
                    severity="warning",
                    action_taken=ResourceAction.WARN,
                    timestamp=now,
                    message=warning
                )
                alerts.append(alert)
        
        for critical in snapshot.critical:
            parts = critical.split(":")
            if len(parts) == 2:
                resource_type = parts[0].strip()
                alert = ResourceAlert(
                    resource_type=resource_type,
                    current_value=0.0,  # Would parse from message
                    limit_value=0.0,
                    severity="critical",
                    action_taken=ResourceAction.DEFER,
                    timestamp=now,
                    message=critical
                )
                alerts.append(alert)
        
        return SuccessResponse(data=alerts)
        
    except Exception as e:
        logger.error(f"Error getting resource alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/predictions", response_model=SuccessResponse[ResourcePredictionsResponse])
async def get_resource_predictions(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Usage predictions.
    
    Get predictive analytics for resource consumption.
    """
    resource_monitor = getattr(request.app.state, 'resource_monitor', None)
    if not resource_monitor:
        raise HTTPException(status_code=503, detail="Resource monitor service not available")
    
    try:
        # Generate predictions based on current usage and trends
        # In a real implementation, this would use historical data and ML
        snapshot = resource_monitor.snapshot
        budget = resource_monitor.budget
        
        predictions = []
        
        # Memory prediction
        memory_trend = "stable"  # Would calculate from history
        memory_growth_rate = 0.05  # 5% per hour estimate
        memory_pred_1h = snapshot.memory_mb * (1 + memory_growth_rate)
        memory_pred_24h = snapshot.memory_mb * (1 + memory_growth_rate * 24)
        memory_time_to_limit = None
        if memory_growth_rate > 0:
            hours_to_limit = (budget.memory_mb.limit - snapshot.memory_mb) / (snapshot.memory_mb * memory_growth_rate)
            if hours_to_limit > 0:
                memory_time_to_limit = hours_to_limit
        
        predictions.append(ResourcePrediction(
            resource_name="memory_mb",
            current_usage=float(snapshot.memory_mb),
            predicted_usage_1h=memory_pred_1h,
            predicted_usage_24h=memory_pred_24h,
            time_to_limit=memory_time_to_limit,
            confidence=0.8,
            trend=memory_trend
        ))
        
        # Token usage prediction (hour)
        # Simple linear projection - would use more sophisticated model
        tokens_per_hour = float(snapshot.tokens_used_hour)
        token_trend = "increasing" if tokens_per_hour > 0 else "stable"
        
        predictions.append(ResourcePrediction(
            resource_name="tokens_hour",
            current_usage=tokens_per_hour,
            predicted_usage_1h=tokens_per_hour * 1.1,  # 10% growth estimate
            predicted_usage_24h=tokens_per_hour,  # Resets each hour
            time_to_limit=1.0 if tokens_per_hour > budget.tokens_hour.warning else None,
            confidence=0.7,
            trend=token_trend
        ))
        
        # Token usage prediction (day)
        tokens_per_day = float(snapshot.tokens_used_day)
        daily_rate = tokens_per_day / 24.0 if tokens_per_day > 0 else 0
        
        predictions.append(ResourcePrediction(
            resource_name="tokens_day",
            current_usage=tokens_per_day,
            predicted_usage_1h=tokens_per_day + daily_rate,
            predicted_usage_24h=tokens_per_day + (daily_rate * 24),
            time_to_limit=(budget.tokens_day.limit - tokens_per_day) / daily_rate if daily_rate > 0 else None,
            confidence=0.75,
            trend="increasing" if daily_rate > 0 else "stable"
        ))
        
        # CPU prediction
        cpu_trend = "stable"
        predictions.append(ResourcePrediction(
            resource_name="cpu_percent",
            current_usage=float(snapshot.cpu_percent),
            predicted_usage_1h=float(snapshot.cpu_average_1m),
            predicted_usage_24h=float(snapshot.cpu_average_1m),
            time_to_limit=None,  # CPU typically fluctuates
            confidence=0.6,
            trend=cpu_trend
        ))
        
        # Active thoughts prediction
        thoughts_trend = "stable"
        predictions.append(ResourcePrediction(
            resource_name="thoughts_active",
            current_usage=float(snapshot.thoughts_active),
            predicted_usage_1h=float(snapshot.thoughts_active),
            predicted_usage_24h=float(snapshot.thoughts_active),
            time_to_limit=None,
            confidence=0.5,
            trend=thoughts_trend
        ))
        
        response = ResourcePredictionsResponse(
            predictions=predictions,
            analysis_window_hours=24,
            generated_at=datetime.now(timezone.utc)
        )
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        logger.error(f"Error generating resource predictions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/alerts/config", response_model=SuccessResponse[AlertConfigurationResponse])
async def configure_resource_alerts(
    request: Request,
    config: AlertConfiguration = Body(...),
    auth: AuthContext = Depends(require_admin)
):
    """
    Configure alerts.
    
    Update resource alert thresholds and actions.
    Requires ADMIN role.
    """
    resource_monitor = getattr(request.app.state, 'resource_monitor', None)
    if not resource_monitor:
        raise HTTPException(status_code=503, detail="Resource monitor service not available")
    
    try:
        # Validate resource name
        valid_resources = ["memory_mb", "cpu_percent", "tokens_hour", "tokens_day", "disk_mb", "thoughts_active"]
        if config.resource_name not in valid_resources:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid resource name. Must be one of: {', '.join(valid_resources)}"
            )
        
        # Get current configuration
        current_limit = getattr(resource_monitor.budget, config.resource_name)
        
        # Store previous config for response
        previous_config = ResourceLimit(
            limit=current_limit.limit,
            warning=current_limit.warning,
            critical=current_limit.critical,
            action=current_limit.action,
            cooldown_seconds=current_limit.cooldown_seconds
        )
        
        # Update configuration
        updated = False
        
        if config.warning_threshold is not None:
            if config.warning_threshold >= current_limit.limit:
                raise HTTPException(
                    status_code=400,
                    detail="Warning threshold must be less than limit"
                )
            current_limit.warning = config.warning_threshold
            updated = True
        
        if config.critical_threshold is not None:
            if config.critical_threshold >= current_limit.limit:
                raise HTTPException(
                    status_code=400,
                    detail="Critical threshold must be less than limit"
                )
            if config.critical_threshold <= current_limit.warning:
                raise HTTPException(
                    status_code=400,
                    detail="Critical threshold must be greater than warning threshold"
                )
            current_limit.critical = config.critical_threshold
            updated = True
        
        if config.action is not None:
            current_limit.action = config.action
            updated = True
        
        if config.cooldown_seconds is not None:
            current_limit.cooldown_seconds = config.cooldown_seconds
            updated = True
        
        # Log the configuration change
        logger.info(
            f"Resource alert configuration updated for {config.resource_name} by {auth.user_id}"
        )
        
        response = AlertConfigurationResponse(
            updated=updated,
            resource_name=config.resource_name,
            new_config=current_limit,
            previous_config=previous_config
        )
        
        return SuccessResponse(data=response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error configuring resource alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))