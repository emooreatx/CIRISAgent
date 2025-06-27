"""
Initialization Service endpoints for CIRIS API v1.

Provides visibility into system startup and initialization sequence.
Read-only endpoints for monitoring system bootstrap.
"""
from typing import Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field

from ciris_engine.schemas.api.responses import SuccessResponse, ErrorResponse, ErrorCode, ErrorDetail
from ciris_engine.schemas.services.lifecycle.initialization import (
    InitializationStatus, InitializationVerification
)
from ciris_engine.schemas.services.operations import InitializationPhase
from ciris_engine.protocols.services.lifecycle.initialization import InitializationServiceProtocol

router = APIRouter(prefix="/init", tags=["initialization"])

# Response schemas specific to initialization endpoints

class InitSequenceStep(BaseModel):
    """A single step in the initialization sequence."""
    phase: str = Field(..., description="Initialization phase this step belongs to")
    name: str = Field(..., description="Step name")
    status: str = Field(..., description="Current status: pending, completed, failed, skipped")
    duration_ms: Optional[int] = Field(None, description="Execution duration in milliseconds")
    error: Optional[str] = Field(None, description="Error message if step failed")

class InitSequenceResponse(BaseModel):
    """Detailed initialization sequence information."""
    phases: List[str] = Field(..., description="All initialization phases in order")
    current_phase: Optional[str] = Field(None, description="Currently executing phase")
    steps: List[InitSequenceStep] = Field(..., description="All initialization steps")
    total_duration_ms: Optional[int] = Field(None, description="Total initialization time")

class ComponentHealth(BaseModel):
    """Health status of a single component."""
    component_name: str = Field(..., description="Name of the component")
    component_type: str = Field(..., description="Type of component (service, handler, etc)")
    is_healthy: bool = Field(..., description="Whether component is healthy")
    is_initialized: bool = Field(..., description="Whether component completed initialization")
    error: Optional[str] = Field(None, description="Error message if unhealthy")

class InitHealthResponse(BaseModel):
    """Initialization health check response."""
    system_ready: bool = Field(..., description="Whether system is fully initialized and ready")
    initialization_complete: bool = Field(..., description="Whether initialization completed")
    components: List[ComponentHealth] = Field(..., description="Health status of all components")
    warnings: List[str] = Field(default_factory=list, description="Non-critical initialization warnings")


@router.get("/status", response_model=SuccessResponse[InitializationStatus])
async def get_initialization_status(request: Request):
    """
    Get current initialization status.
    
    Returns the overall status of system initialization including:
    - Whether initialization is complete
    - Start time and duration
    - Status of each phase
    - List of completed steps
    - Any errors encountered
    """
    # Get initialization service from app state
    if not hasattr(request.app.state, 'initialization_service'):
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.SERVICE_UNAVAILABLE,
                    message="Initialization service not available"
                )
            ).model_dump()
        )
    
    init_service: InitializationServiceProtocol = request.app.state.initialization_service
    
    try:
        status = await init_service.get_initialization_status()
        return SuccessResponse(data=status)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Failed to get initialization status: {str(e)}"
                )
            ).model_dump()
        )


@router.get("/sequence", response_model=SuccessResponse[InitSequenceResponse])
async def get_initialization_sequence(request: Request):
    """
    Get detailed initialization sequence.
    
    Returns the complete initialization sequence showing:
    - All phases and their order
    - Individual steps within each phase
    - Current execution status
    - Timing information for completed steps
    
    This endpoint provides granular visibility into the startup process.
    """
    # Get initialization service from app state
    if not hasattr(request.app.state, 'initialization_service'):
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.SERVICE_UNAVAILABLE,
                    message="Initialization service not available"
                )
            ).model_dump()
        )
    
    init_service: InitializationServiceProtocol = request.app.state.initialization_service
    
    try:
        # Get current status
        status = await init_service.get_initialization_status()
        
        # Build sequence response
        phases = [phase.value for phase in InitializationPhase]
        
        # Determine current phase
        current_phase = None
        for phase, phase_status in status.phase_status.items():
            if phase_status == "in_progress":
                current_phase = phase
                break
        
        # Build step list
        steps: List[InitSequenceStep] = []
        
        # Map completed steps to their status
        completed_set = set(status.completed_steps)
        
        # Note: The initialization service doesn't expose all registered steps,
        # only completed ones. In a real implementation, we'd need to enhance
        # the service to track all steps.
        for step_path in status.completed_steps:
            if "/" in step_path:
                phase, name = step_path.split("/", 1)
                steps.append(InitSequenceStep(
                    phase=phase,
                    name=name,
                    status="completed",
                    duration_ms=None,  # Service doesn't track individual durations
                    error=None
                ))
        
        # Calculate total duration
        total_duration_ms = None
        if status.duration_seconds is not None:
            total_duration_ms = int(status.duration_seconds * 1000)
        
        response = InitSequenceResponse(
            phases=phases,
            current_phase=current_phase,
            steps=steps,
            total_duration_ms=total_duration_ms
        )
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Failed to get initialization sequence: {str(e)}"
                )
            ).model_dump()
        )


@router.get("/health", response_model=SuccessResponse[InitHealthResponse])
async def get_initialization_health(request: Request):
    """
    Get initialization health check.
    
    Returns the health status of system initialization and all components.
    This is useful for monitoring tools to ensure the system started correctly.
    
    The response includes:
    - Overall system readiness
    - Individual component health
    - Any warnings from initialization
    """
    # Get initialization service from app state
    if not hasattr(request.app.state, 'initialization_service'):
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.SERVICE_UNAVAILABLE,
                    message="Initialization service not available"
                )
            ).model_dump()
        )
    
    init_service: InitializationServiceProtocol = request.app.state.initialization_service
    
    try:
        # Get verification status
        verification = await init_service.verify_initialization()
        status = await init_service.get_initialization_status()
        
        # Build component health list
        components: List[ComponentHealth] = []
        
        # Add initialization service itself
        init_service_health = await init_service.is_healthy()
        components.append(ComponentHealth(
            component_name="InitializationService",
            component_type="service",
            is_healthy=init_service_health,
            is_initialized=True,  # It's running this check
            error=None
        ))
        
        # Check other services if available
        if hasattr(request.app.state, 'service_registry'):
            service_registry = request.app.state.service_registry
            
            # Get all registered services
            from ciris_engine.schemas.runtime.enums import ServiceType
            for service_type in ServiceType:
                try:
                    providers = service_registry.get_services_by_type(service_type)
                    for provider in providers:
                        component_name = provider.__class__.__name__
                        is_healthy = True
                        error = None
                        
                        # Check health if method exists
                        if hasattr(provider, 'is_healthy'):
                            try:
                                import asyncio
                                if asyncio.iscoroutinefunction(provider.is_healthy):
                                    is_healthy = await provider.is_healthy()
                                else:
                                    is_healthy = provider.is_healthy()
                            except Exception as e:
                                is_healthy = False
                                error = str(e)
                        
                        components.append(ComponentHealth(
                            component_name=component_name,
                            component_type=service_type.value,
                            is_healthy=is_healthy,
                            is_initialized=True,  # Assume initialized if registered
                            error=error
                        ))
                except Exception as e:
                    # Log but continue
                    pass
        
        # Build warnings list
        warnings: List[str] = []
        
        # Check for non-critical issues
        if verification.system_initialized and not verification.all_steps_completed:
            warnings.append("Some initialization steps were skipped")
        
        if status.error and verification.system_initialized:
            warnings.append(f"Non-critical error during initialization: {status.error}")
        
        # Determine overall readiness
        system_ready = (
            verification.system_initialized and
            verification.no_errors and
            all(c.is_healthy for c in components if c.component_type != "test")
        )
        
        response = InitHealthResponse(
            system_ready=system_ready,
            initialization_complete=status.complete,
            components=components,
            warnings=warnings
        )
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Failed to get initialization health: {str(e)}"
                )
            ).model_dump()
        )