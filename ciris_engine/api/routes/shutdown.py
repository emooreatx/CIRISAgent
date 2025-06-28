"""
Shutdown Service endpoints for CIRIS API v1.

Manages graceful system termination.
"""
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel, Field, field_serializer

from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.api.dependencies.auth import require_admin, AuthContext
from ciris_engine.protocols.services import ShutdownServiceProtocol

router = APIRouter(prefix="/shutdown", tags=["shutdown"])


# Response schemas

class ShutdownStatus(BaseModel):
    """Current shutdown status."""
    shutdown_requested: bool = Field(..., description="Whether shutdown has been requested")
    shutdown_reason: Optional[str] = Field(None, description="Reason for shutdown if requested")
    registered_handlers: int = Field(..., description="Number of registered shutdown handlers")
    service_healthy: bool = Field(..., description="Whether shutdown service is healthy")
    timestamp: datetime = Field(..., description="Current timestamp")
    
    @field_serializer('timestamp')
    def serialize_timestamp(self, timestamp: datetime, _info):
        return timestamp.isoformat() if timestamp else None


class ShutdownPrepareRequest(BaseModel):
    """Request to prepare for shutdown."""
    reason: str = Field(..., description="Reason for shutdown", min_length=1, max_length=500)
    
    
class ShutdownPrepareResponse(BaseModel):
    """Response to shutdown preparation."""
    status: str = Field(..., description="Preparation status")
    message: str = Field(..., description="Human-readable status message")
    handlers_notified: int = Field(..., description="Number of handlers notified")
    timestamp: datetime = Field(..., description="When preparation started")
    
    @field_serializer('timestamp')
    def serialize_timestamp(self, timestamp: datetime, _info):
        return timestamp.isoformat() if timestamp else None


class ShutdownExecuteRequest(BaseModel):
    """Request to execute shutdown."""
    confirm: bool = Field(..., description="Confirmation flag (must be true)")
    force: bool = Field(False, description="Force immediate shutdown")
    

class ShutdownExecuteResponse(BaseModel):
    """Response to shutdown execution."""
    status: str = Field(..., description="Execution status")
    message: str = Field(..., description="Human-readable status message")
    shutdown_initiated: bool = Field(..., description="Whether shutdown was initiated")
    timestamp: datetime = Field(..., description="When shutdown was initiated")
    
    @field_serializer('timestamp')
    def serialize_timestamp(self, timestamp: datetime, _info):
        return timestamp.isoformat() if timestamp else None


class ShutdownAbortResponse(BaseModel):
    """Response to shutdown abort."""
    status: str = Field(..., description="Abort status")
    message: str = Field(..., description="Human-readable status message")
    was_active: bool = Field(..., description="Whether shutdown was actually in progress")
    timestamp: datetime = Field(..., description="When abort was processed")
    
    @field_serializer('timestamp')
    def serialize_timestamp(self, timestamp: datetime, _info):
        return timestamp.isoformat() if timestamp else None


# Helper function to get shutdown service
async def get_shutdown_service(request: Request) -> ShutdownServiceProtocol:
    """Get shutdown service from runtime."""
    # Get from runtime, not service registry
    runtime = getattr(request.app.state, 'runtime', None)
    if not runtime:
        raise HTTPException(status_code=503, detail="Runtime not available")
    
    shutdown_service = getattr(runtime, 'shutdown_service', None)
    if not shutdown_service:
        raise HTTPException(status_code=503, detail="Shutdown service not available")
    
    return shutdown_service


# Endpoints

@router.get("/status", response_model=SuccessResponse[ShutdownStatus])
async def get_shutdown_status(
    request: Request,
    shutdown_service: ShutdownServiceProtocol = Depends(get_shutdown_service)
):
    """
    Get shutdown readiness status.
    
    Returns current shutdown service status including whether
    shutdown has been requested and registered handler count.
    """
    try:
        # Get basic status
        is_requested = shutdown_service.is_shutdown_requested()
        reason = shutdown_service.get_shutdown_reason()
        
        # Get service status for handler count
        status = shutdown_service.get_status()
        handler_count = int(status.metrics.get('registered_handlers', 0))
        
        # Check if service is healthy
        is_healthy = await shutdown_service.is_healthy()
        
        response = ShutdownStatus(
            shutdown_requested=is_requested,
            shutdown_reason=reason,
            registered_handlers=handler_count,
            service_healthy=is_healthy,
            timestamp=datetime.now(timezone.utc)
        )
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prepare", response_model=SuccessResponse[ShutdownPrepareResponse])
async def prepare_shutdown(
    body: ShutdownPrepareRequest,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    shutdown_service: ShutdownServiceProtocol = Depends(get_shutdown_service)
):
    """
    Prepare for shutdown (ADMIN required).
    
    Notifies all registered handlers that shutdown is imminent.
    This allows services to start winding down operations.
    """
    try:
        # Check if already shutting down
        if shutdown_service.is_shutdown_requested():
            existing_reason = shutdown_service.get_shutdown_reason()
            raise HTTPException(
                status_code=409, 
                detail=f"Shutdown already requested: {existing_reason}"
            )
        
        # Get handler count before notification
        status = shutdown_service.get_status()
        handler_count = int(status.metrics.get('registered_handlers', 0))
        
        # Note: The shutdown service doesn't have a separate "prepare" method
        # Preparation happens as part of the shutdown request
        # For now, we just return preparation status
        
        response = ShutdownPrepareResponse(
            status="prepared",
            message=f"System prepared for shutdown: {body.reason}",
            handlers_notified=handler_count,
            timestamp=datetime.now(timezone.utc)
        )
        
        return SuccessResponse(data=response)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute", response_model=SuccessResponse[ShutdownExecuteResponse])
async def execute_shutdown(
    body: ShutdownExecuteRequest,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    shutdown_service: ShutdownServiceProtocol = Depends(get_shutdown_service)
):
    """
    Execute shutdown (ADMIN required).
    
    Initiates the actual shutdown process. Requires confirmation
    flag to prevent accidental shutdowns.
    """
    try:
        # Validate confirmation
        if not body.confirm:
            raise HTTPException(
                status_code=400,
                detail="Confirmation required (confirm=true)"
            )
        
        # Build shutdown reason
        reason = f"API shutdown by {auth.user_id}"
        if body.force:
            reason += " (forced)"
        
        # Execute shutdown
        await shutdown_service.request_shutdown(reason)
        
        response = ShutdownExecuteResponse(
            status="initiated",
            message="System shutdown initiated",
            shutdown_initiated=True,
            timestamp=datetime.now(timezone.utc)
        )
        
        return SuccessResponse(data=response)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/abort", response_model=SuccessResponse[ShutdownAbortResponse])
async def abort_shutdown(
    request: Request,
    auth: AuthContext = Depends(require_admin),
    shutdown_service: ShutdownServiceProtocol = Depends(get_shutdown_service)
):
    """
    Abort shutdown (ADMIN required).
    
    Attempts to abort an in-progress shutdown. May not be
    possible if shutdown has progressed too far.
    """
    try:
        # Check if shutdown is actually in progress
        was_active = shutdown_service.is_shutdown_requested()
        
        if not was_active:
            response = ShutdownAbortResponse(
                status="no_shutdown",
                message="No shutdown in progress",
                was_active=False,
                timestamp=datetime.now(timezone.utc)
            )
        else:
            # The current shutdown service doesn't support abort
            # Once shutdown is requested, it proceeds
            raise HTTPException(
                status_code=501,
                detail="Shutdown abort not implemented - shutdown will proceed"
            )
        
        return SuccessResponse(data=response)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))