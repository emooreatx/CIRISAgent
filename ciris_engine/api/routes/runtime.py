"""
Runtime Control service endpoints for CIRIS API v1.

Controls agent runtime behavior (requires ADMIN).
"""
from typing import List, Optional, Dict
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel, Field

from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.schemas.services.core.runtime import (
    ProcessorControlResponse,
    ProcessorQueueStatus,
    RuntimeStatusResponse,
    RuntimeStateSnapshot,
    ServiceHealthStatus,
    RuntimeEvent
)
# CognitiveState import removed - using string values directly
from ciris_engine.api.dependencies.auth import require_admin, require_authority, AuthContext
from ciris_engine.schemas.api.runtime import StateTransitionResult, ProcessingSpeedResult
from ciris_engine.schemas.api.agent import ActiveTask

router = APIRouter(prefix="/runtime", tags=["runtime"])

# Request schemas

class PauseRequest(BaseModel):
    """Request to pause processing."""
    reason: Optional[str] = Field(None, description="Reason for pausing")

class ResumeRequest(BaseModel):
    """Request to resume processing."""
    reason: Optional[str] = Field(None, description="Reason for resuming")

class StateChangeRequest(BaseModel):
    """Request to change cognitive state."""
    target_state: str = Field(..., description="Target cognitive state (WAKEUP, WORK, PLAY, SOLITUDE, DREAM, SHUTDOWN)")
    reason: Optional[str] = Field(None, description="Reason for state change")

class EmergencyStopRequest(BaseModel):
    """Request for emergency stop."""
    reason: str = Field(..., description="Reason for emergency stop")
    force: bool = Field(False, description="Force immediate stop")

class StateTransitionRequest(BaseModel):
    """Request to transition processor state."""
    reason: str = Field(..., description="Reason for state transition")

class ProcessingSpeedRequest(BaseModel):
    """Request to set processing speed."""
    multiplier: float = Field(..., ge=0.1, le=10.0, description="Speed multiplier (1.0 = normal)")

# Endpoints

@router.get("/status", response_model=SuccessResponse[RuntimeStatusResponse])
async def get_runtime_status(
    request: Request,
    auth: AuthContext = Depends(require_admin)
):
    """
    Runtime status.

    Get current runtime operational status.
    """
    runtime_control = getattr(request.app.state, 'runtime_control', None)
    if not runtime_control:
        raise HTTPException(status_code=503, detail="Runtime control service not available")

    try:
        status = await runtime_control.get_runtime_status()
        return SuccessResponse(data=status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/pause", response_model=SuccessResponse[ProcessorControlResponse])
async def pause_processing(
    request: Request,
    body: PauseRequest,
    auth: AuthContext = Depends(require_admin)
):
    """
    Pause processing.

    Pause agent message processing.
    """
    runtime_control = getattr(request.app.state, 'runtime_control', None)
    if not runtime_control:
        raise HTTPException(status_code=503, detail="Runtime control service not available")

    try:
        result = await runtime_control.pause_processing()
        return SuccessResponse(data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/resume", response_model=SuccessResponse[ProcessorControlResponse])
async def resume_processing(
    request: Request,
    body: ResumeRequest,
    auth: AuthContext = Depends(require_admin)
):
    """
    Resume processing.

    Resume agent message processing.
    """
    runtime_control = getattr(request.app.state, 'runtime_control', None)
    if not runtime_control:
        raise HTTPException(status_code=503, detail="Runtime control service not available")

    try:
        result = await runtime_control.resume_processing()
        return SuccessResponse(data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/single-step", response_model=SuccessResponse[ProcessorControlResponse])
async def single_step_processing(
    request: Request,
    auth: AuthContext = Depends(require_admin)
):
    """
    Single step processing.

    Execute a single processing step and pause.
    Useful for debugging and step-through analysis.
    """
    runtime_control = getattr(request.app.state, 'runtime_control', None)
    if not runtime_control:
        raise HTTPException(status_code=503, detail="Runtime control service not available")

    try:
        result = await runtime_control.single_step()
        return SuccessResponse(data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/state", response_model=SuccessResponse[ProcessorControlResponse])
async def change_cognitive_state(
    request: Request,
    body: StateChangeRequest,
    auth: AuthContext = Depends(require_admin)
):
    """
    Change cognitive state.

    Transition agent to a different cognitive state.
    """
    runtime_control = getattr(request.app.state, 'runtime_control', None)
    if not runtime_control:
        raise HTTPException(status_code=503, detail="Runtime control service not available")

    try:
        # Use runtime control to change state
        # This is a simplified version - actual implementation may vary
        if hasattr(runtime_control, 'change_cognitive_state'):
            result = await runtime_control.change_cognitive_state(
                body.target_state,
                reason=body.reason
            )
        else:
            # Fallback response
            result = ProcessorControlResponse(
                success=False,
                message="State change not implemented",
                processor_state="running",
                queue_depth=0
            )

        return SuccessResponse(data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tasks", response_model=SuccessResponse[List[ActiveTask]])
async def get_active_tasks(
    request: Request,
    auth: AuthContext = Depends(require_admin)
):
    """
    Active tasks.

    Get list of currently active tasks.
    """
    runtime_control = getattr(request.app.state, 'runtime_control', None)
    if not runtime_control:
        raise HTTPException(status_code=503, detail="Runtime control service not available")

    try:
        # Get queue status which includes task info
        queue_status = await runtime_control.get_processor_queue_status()

        # Extract active tasks
        tasks = []
        if hasattr(queue_status, 'active_tasks'):
            tasks = queue_status.active_tasks
        elif hasattr(queue_status, 'pending_tasks'):
            # Use pending tasks as proxy
            for i, task in enumerate(queue_status.pending_tasks[:10]):
                tasks.append(ActiveTask(
                    task_id=f"task_{i}",
                    type="processing",
                    status="active" if i == 0 else "pending",
                    description=None,
                    created_at=datetime.now(timezone.utc),
                    priority=None
                ))

        return SuccessResponse(data=tasks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/emergency-stop", response_model=SuccessResponse[ProcessorControlResponse])
async def emergency_stop(
    request: Request,
    body: EmergencyStopRequest,
    auth: AuthContext = Depends(require_admin)
):
    """
    Emergency stop.

    Immediately stop all agent processing.
    """
    runtime_control = getattr(request.app.state, 'runtime_control', None)
    if not runtime_control:
        raise HTTPException(status_code=503, detail="Runtime control service not available")

    try:
        # Log emergency stop
        import logging
        logger = logging.getLogger(__name__)
        logger.critical(f"EMERGENCY STOP requested by {auth.user_id}: {body.reason}")

        # Shutdown runtime
        result = await runtime_control.shutdown_runtime(body.reason)

        return SuccessResponse(data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/events", response_model=SuccessResponse[List[RuntimeEvent]])
async def get_runtime_events(
    request: Request,
    limit: int = 100,
    auth: AuthContext = Depends(require_admin)
):
    """
    Runtime events.

    Get recent runtime events for debugging.
    """
    runtime_control = getattr(request.app.state, 'runtime_control', None)
    if not runtime_control:
        raise HTTPException(status_code=503, detail="Runtime control service not available")

    try:
        events = runtime_control.get_events_history(limit=limit)
        return SuccessResponse(data=events)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health", response_model=SuccessResponse[ServiceHealthStatus])
async def get_service_health(
    request: Request,
    auth: AuthContext = Depends(require_admin)
):
    """
    Service health status.

    Get comprehensive health status of all services.
    """
    runtime_control = getattr(request.app.state, 'runtime_control', None)
    if not runtime_control:
        raise HTTPException(status_code=503, detail="Runtime control service not available")

    try:
        health = await runtime_control.get_service_health_status()
        return SuccessResponse(data=health)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/snapshot", response_model=SuccessResponse[RuntimeStateSnapshot])
async def get_runtime_snapshot(
    request: Request,
    auth: AuthContext = Depends(require_admin)
):
    """
    Runtime state snapshot.

    Get complete snapshot of runtime state.
    """
    runtime_control = getattr(request.app.state, 'runtime_control', None)
    if not runtime_control:
        raise HTTPException(status_code=503, detail="Runtime control service not available")

    try:
        snapshot = await runtime_control.get_runtime_snapshot()
        return SuccessResponse(data=snapshot)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/state/{state}", response_model=SuccessResponse[StateTransitionResult])
async def force_state_transition(
    request: Request,
    state: str,
    body: StateTransitionRequest,
    auth: AuthContext = Depends(require_authority)
):
    """
    Force state transition.

    Force the processor to transition to a specific state.
    Requires AUTHORITY role as this can disrupt normal processing.

    Valid states: WAKEUP, WORK, PLAY, SOLITUDE, DREAM, SHUTDOWN
    """
    runtime_control = getattr(request.app.state, 'runtime_control', None)
    if not runtime_control:
        raise HTTPException(status_code=503, detail="Runtime control not available")

    try:
        # Validate state
        valid_states = ["WAKEUP", "WORK", "PLAY", "SOLITUDE", "DREAM", "SHUTDOWN"]
        if state.upper() not in valid_states:
            raise HTTPException(status_code=400, detail=f"Invalid state. Must be one of: {', '.join(valid_states)}")

        # Get agent processor
        if not hasattr(runtime_control, 'runtime') or not hasattr(runtime_control.runtime, 'agent_processor'):
            raise HTTPException(status_code=503, detail="Agent processor not available")

        processor = runtime_control.runtime.agent_processor

        # Force state transition
        success = await processor.force_state_transition(state.upper(), body.reason)

        # Get new state
        current_state = processor.get_current_state()

        result = StateTransitionResult(
            success=success,
            target_state=state.upper(),
            current_state=current_state,
            reason=body.reason,
            transition_time_ms=None  # Would measure in real implementation
        )

        return SuccessResponse(data=result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/queue", response_model=SuccessResponse[ProcessorQueueStatus])
async def get_queue_status(
    request: Request,
    auth: AuthContext = Depends(require_admin)
):
    """
    Get processing queue status.

    Returns detailed information about the processing queue including
    pending items, active processing, and priority distribution.
    """
    runtime_control = getattr(request.app.state, 'runtime_control', None)
    if not runtime_control:
        raise HTTPException(status_code=503, detail="Runtime control not available")

    try:
        # Get agent processor
        if not hasattr(runtime_control, 'runtime') or not hasattr(runtime_control.runtime, 'agent_processor'):
            raise HTTPException(status_code=503, detail="Agent processor not available")

        processor = runtime_control.runtime.agent_processor

        # Get queue status
        queue_status = processor.get_queue_status()

        # Convert to API schema if needed
        if hasattr(queue_status, '__dict__'):
            # It's a protocol object, convert to dict
            status_data = {
                "pending_thoughts": queue_status.pending_thoughts,
                "pending_tasks": queue_status.pending_tasks,
                "active_thoughts": queue_status.active_thoughts,
                "active_tasks": queue_status.active_tasks,
                "blocked_items": queue_status.blocked_items,
                "priority_distribution": queue_status.priority_distribution
            }
            queue_status = ProcessorQueueStatus(**status_data)

        return SuccessResponse(data=queue_status)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/speed", response_model=SuccessResponse[ProcessingSpeedResult])
async def set_processing_speed(
    request: Request,
    body: ProcessingSpeedRequest,
    auth: AuthContext = Depends(require_admin)
):
    """
    Set processing speed.

    Adjust the processing speed multiplier.
    - 1.0 = normal speed
    - 0.5 = half speed
    - 2.0 = double speed

    Requires ADMIN role.
    """
    runtime_control = getattr(request.app.state, 'runtime_control', None)
    if not runtime_control:
        raise HTTPException(status_code=503, detail="Runtime control not available")

    try:
        # Get agent processor
        if not hasattr(runtime_control, 'runtime') or not hasattr(runtime_control.runtime, 'agent_processor'):
            raise HTTPException(status_code=503, detail="Agent processor not available")

        processor = runtime_control.runtime.agent_processor

        # Set processing speed
        await processor.set_processing_speed(body.multiplier)

        result = ProcessingSpeedResult(
            success=True,
            multiplier=body.multiplier,
            description=f"Processing speed set to {body.multiplier}x",
            effective_immediately=True
        )

        return SuccessResponse(data=result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
