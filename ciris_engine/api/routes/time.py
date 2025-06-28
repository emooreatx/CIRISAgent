"""
Time Service endpoints for CIRIS API v1.

Ensures temporal consistency across the system.
"""
from fastapi import APIRouter, Request, HTTPException
from datetime import datetime, timezone
from typing import Optional

from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.schemas.services.lifecycle.time import TimeSnapshot, TimeServiceStatus
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from pydantic import BaseModel, Field, field_serializer

router = APIRouter(prefix="/time", tags=["time"])

class CurrentTimeResponse(BaseModel):
    """Current system time response."""
    current_time: datetime = Field(..., description="Current time in UTC")
    current_iso: str = Field(..., description="Current time as ISO string")
    current_timestamp: float = Field(..., description="Current Unix timestamp")
    
    @field_serializer('current_time')
    def serialize_current_time(self, current_time: datetime, _info):
        return current_time.isoformat() if current_time else None

class UptimeResponse(BaseModel):
    """Service uptime response."""
    service_name: str = Field(default="TimeService")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")
    start_time: datetime = Field(..., description="Service start time")
    current_time: datetime = Field(..., description="Current time")
    
    @field_serializer('start_time', 'current_time')
    def serialize_times(self, dt: datetime, _info):
        return dt.isoformat() if dt else None

class TimeSyncStatus(BaseModel):
    """Time synchronization status."""
    is_synchronized: bool = Field(..., description="Whether time is synchronized")
    sync_source: str = Field(default="system", description="Time synchronization source")
    last_sync: Optional[datetime] = Field(None, description="Last synchronization time")
    drift_ms: float = Field(0.0, description="Time drift in milliseconds")
    is_mocked: bool = Field(..., description="Whether time is mocked for testing")
    
    @field_serializer('last_sync')
    def serialize_last_sync(self, last_sync: Optional[datetime], _info):
        return last_sync.isoformat() if last_sync else None

@router.get("/current", response_model=SuccessResponse[CurrentTimeResponse])
async def get_current_time(request: Request):
    """
    Current system time.
    
    Get the current system time in multiple formats.
    """
    # Get time service directly (it's a single-instance service)
    time_service: Optional[TimeServiceProtocol] = getattr(request.app.state, 'time_service', None)
    if not time_service:
        raise HTTPException(status_code=503, detail="Time service not available")
    
    try:
        current_time = time_service.now()
        current_iso = time_service.now_iso()
        current_timestamp = time_service.timestamp()
        
        response = CurrentTimeResponse(
            current_time=current_time,
            current_iso=current_iso,
            current_timestamp=current_timestamp
        )
        
        return SuccessResponse(data=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get current time: {str(e)}")

@router.get("/uptime", response_model=SuccessResponse[UptimeResponse])
async def get_service_uptime(request: Request):
    """
    Service uptime.
    
    Get the time service uptime and start time.
    """
    # Get time service
    time_service: Optional[TimeServiceProtocol] = getattr(request.app.state, 'time_service', None)
    if not time_service:
        raise HTTPException(status_code=503, detail="Time service not available")
    
    try:
        # Get current time
        current_time = time_service.now()
        
        # Get service start time if available
        start_time = getattr(time_service, '_start_time', None)
        if not start_time:
            # If no start time tracked, use current time
            start_time = current_time
            uptime_seconds = 0.0
        else:
            # Calculate uptime
            uptime_seconds = (current_time - start_time).total_seconds()
        
        response = UptimeResponse(
            service_name="TimeService",
            uptime_seconds=uptime_seconds,
            start_time=start_time,
            current_time=current_time
        )
        
        return SuccessResponse(data=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get uptime: {str(e)}")

@router.get("/sync", response_model=SuccessResponse[TimeSyncStatus])
async def get_time_sync_status(request: Request):
    """
    Time sync status.
    
    Get the time synchronization status and configuration.
    """
    # Get time service
    time_service: Optional[TimeServiceProtocol] = getattr(request.app.state, 'time_service', None)
    if not time_service:
        raise HTTPException(status_code=503, detail="Time service not available")
    
    try:
        # Check if time is mocked
        is_mocked = getattr(time_service, '_mock_time', None) is not None
        
        # Get last sync time if tracked
        last_sync = getattr(time_service, '_last_sync', None)
        
        # For now, we always report as synchronized unless mocked
        # In a real system, this would check NTP or other time sources
        is_synchronized = not is_mocked
        
        response = TimeSyncStatus(
            is_synchronized=is_synchronized,
            sync_source="mock" if is_mocked else "system",
            last_sync=last_sync,
            drift_ms=0.0,  # No drift tracking in current implementation
            is_mocked=is_mocked
        )
        
        return SuccessResponse(data=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sync status: {str(e)}")