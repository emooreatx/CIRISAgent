"""
System management endpoint extensions for CIRIS API v1.

Adds runtime queue, service management, and processor state endpoints.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.schemas.services.core.runtime import (
    ProcessorQueueStatus,
    ServiceHealthStatus,
    ServiceSelectionExplanation,
)

from ..constants import (
    DESC_CURRENT_COGNITIVE_STATE,
    DESC_HUMAN_READABLE_STATUS,
    ERROR_RUNTIME_CONTROL_SERVICE_NOT_AVAILABLE,
)
from ..dependencies.auth import AuthContext, require_admin, require_observer

router = APIRouter(prefix="/system", tags=["system-extensions"])
logger = logging.getLogger(__name__)


# Runtime Control Extensions


@router.get("/runtime/queue", response_model=SuccessResponse[ProcessorQueueStatus])
async def get_processing_queue_status(
    request: Request, auth: AuthContext = Depends(require_observer)
) -> SuccessResponse[ProcessorQueueStatus]:
    """
    Get processing queue status.

    Returns information about pending thoughts, tasks, and processing metrics.
    """
    # Try main runtime control service first (has all methods), fall back to API runtime control
    runtime_control = getattr(request.app.state, "main_runtime_control_service", None)
    if not runtime_control:
        runtime_control = getattr(request.app.state, "runtime_control_service", None)
    if not runtime_control:
        raise HTTPException(status_code=503, detail=ERROR_RUNTIME_CONTROL_SERVICE_NOT_AVAILABLE)

    try:
        queue_status = await runtime_control.get_processor_queue_status()
        return SuccessResponse(data=queue_status)
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class RuntimeControlResponse(BaseModel):
    """Response to runtime control actions."""

    success: bool = Field(..., description="Whether action succeeded")
    message: str = Field(..., description=DESC_HUMAN_READABLE_STATUS)
    processor_state: str = Field(..., description="Current processor state")
    cognitive_state: Optional[str] = Field(None, description=DESC_CURRENT_COGNITIVE_STATE)
    queue_depth: int = Field(0, description="Number of items in processing queue")


@router.post("/runtime/single-step", response_model=SuccessResponse[RuntimeControlResponse])
async def single_step_processor(
    request: Request, auth: AuthContext = Depends(require_admin), body: dict = Body(default={})
) -> SuccessResponse[RuntimeControlResponse]:
    """
    Execute a single processing step.

    Useful for debugging and demonstrations. Processes one item from the queue.
    Requires ADMIN role.
    """
    # Try main runtime control service first (has all methods), fall back to API runtime control
    runtime_control = getattr(request.app.state, "main_runtime_control_service", None)
    if not runtime_control:
        runtime_control = getattr(request.app.state, "runtime_control_service", None)
    if not runtime_control:
        raise HTTPException(status_code=503, detail=ERROR_RUNTIME_CONTROL_SERVICE_NOT_AVAILABLE)

    try:
        result = await runtime_control.single_step()

        # Convert to our response format
        response = RuntimeControlResponse(
            success=result.success,
            message=f"Single step {'completed' if result.success else 'failed'}: {result.error or 'No additional info'}",
            processor_state=result.new_status.value if hasattr(result.new_status, "value") else str(result.new_status),
            cognitive_state=None,  # Would need to get from agent processor
            queue_depth=0,  # Would need to get from queue status
        )

        return SuccessResponse(data=response)
    except Exception as e:
        logger.error(f"Error in single step: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Service Management Extensions


class ServicePriorityUpdateRequest(BaseModel):
    """Request to update service priority."""

    priority: str = Field(..., description="New priority level (CRITICAL, HIGH, NORMAL, LOW, FALLBACK)")
    priority_group: Optional[int] = Field(None, description="Priority group (0, 1, 2...)")
    strategy: Optional[str] = Field(None, description="Selection strategy (FALLBACK, ROUND_ROBIN)")


@router.get("/services/health", response_model=SuccessResponse[ServiceHealthStatus])
async def get_service_health_details(
    request: Request, auth: AuthContext = Depends(require_observer)
) -> SuccessResponse[ServiceHealthStatus]:
    """
    Get detailed service health status.

    Returns comprehensive health information including circuit breaker states,
    error rates, and recommendations.
    """
    # Try main runtime control service first (has all methods), fall back to API runtime control
    runtime_control = getattr(request.app.state, "main_runtime_control_service", None)
    if not runtime_control:
        runtime_control = getattr(request.app.state, "runtime_control_service", None)
    if not runtime_control:
        raise HTTPException(status_code=503, detail=ERROR_RUNTIME_CONTROL_SERVICE_NOT_AVAILABLE)

    try:
        health_status = await runtime_control.get_service_health_status()
        return SuccessResponse(data=health_status)
    except Exception as e:
        logger.error(f"Error getting service health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ServicePriorityUpdateResponse(BaseModel):
    """Response from service priority update."""

    provider_name: str = Field(..., description="Provider name that was updated")
    old_priority: str = Field(..., description="Previous priority level")
    new_priority: str = Field(..., description="New priority level")
    old_priority_group: Optional[int] = Field(None, description="Previous priority group")
    new_priority_group: Optional[int] = Field(None, description="New priority group")
    old_strategy: Optional[str] = Field(None, description="Previous selection strategy")
    new_strategy: Optional[str] = Field(None, description="New selection strategy")
    message: str = Field(..., description="Status message")


@router.put("/services/{provider_name}/priority", response_model=SuccessResponse[ServicePriorityUpdateResponse])
async def update_service_priority(
    provider_name: str, body: ServicePriorityUpdateRequest, request: Request, auth: AuthContext = Depends(require_admin)
) -> SuccessResponse[ServicePriorityUpdateResponse]:
    """
    Update service provider priority.

    Changes the priority, priority group, and/or selection strategy for a service provider.
    Requires ADMIN role.
    """
    # Try main runtime control service first (has all methods), fall back to API runtime control
    runtime_control = getattr(request.app.state, "main_runtime_control_service", None)
    if not runtime_control:
        runtime_control = getattr(request.app.state, "runtime_control_service", None)
    if not runtime_control:
        raise HTTPException(status_code=503, detail=ERROR_RUNTIME_CONTROL_SERVICE_NOT_AVAILABLE)

    try:
        result = await runtime_control.update_service_priority(
            provider_name=provider_name,
            new_priority=body.priority,
            new_priority_group=body.priority_group,
            new_strategy=body.strategy,
        )
        # Convert the result dict to our typed response
        response = ServicePriorityUpdateResponse(
            provider_name=result.get("provider_name", provider_name),
            old_priority=result.get("old_priority", "NORMAL"),
            new_priority=result.get("new_priority", body.priority),
            old_priority_group=result.get("old_priority_group"),
            new_priority_group=result.get("new_priority_group"),
            old_strategy=result.get("old_strategy"),
            new_strategy=result.get("new_strategy"),
            message=result.get("message", "Priority updated successfully"),
        )
        return SuccessResponse(data=response)
    except Exception as e:
        logger.error(f"Error updating service priority: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class CircuitBreakerResetRequest(BaseModel):
    """Request to reset circuit breakers."""

    service_type: Optional[str] = Field(None, description="Specific service type to reset, or all if not specified")


class CircuitBreakerResetResponse(BaseModel):
    """Response from circuit breaker reset."""

    service_type: Optional[str] = Field(None, description="Service type that was reset")
    reset_count: int = Field(..., description="Number of circuit breakers reset")
    services_affected: List[str] = Field(default_factory=list, description="List of affected services")
    message: str = Field(..., description="Status message")


@router.post("/services/circuit-breakers/reset", response_model=SuccessResponse[CircuitBreakerResetResponse])
async def reset_service_circuit_breakers(
    body: CircuitBreakerResetRequest, request: Request, auth: AuthContext = Depends(require_admin)
) -> SuccessResponse[CircuitBreakerResetResponse]:
    """
    Reset circuit breakers.

    Resets circuit breakers for specified service type or all services.
    Useful for recovering from transient failures.
    Requires ADMIN role.
    """
    # Try main runtime control service first (has all methods), fall back to API runtime control
    runtime_control = getattr(request.app.state, "main_runtime_control_service", None)
    if not runtime_control:
        runtime_control = getattr(request.app.state, "runtime_control_service", None)
    if not runtime_control:
        raise HTTPException(status_code=503, detail=ERROR_RUNTIME_CONTROL_SERVICE_NOT_AVAILABLE)

    try:
        result = await runtime_control.reset_circuit_breakers(body.service_type)
        # Convert the result dict to our typed response
        response = CircuitBreakerResetResponse(
            service_type=body.service_type,
            reset_count=result.get("reset_count", 0),
            services_affected=result.get("services_affected", []),
            message=result.get("message", "Circuit breakers reset successfully"),
        )
        return SuccessResponse(data=response)
    except Exception as e:
        logger.error(f"Error resetting circuit breakers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/services/selection-logic", response_model=SuccessResponse[ServiceSelectionExplanation])
async def get_service_selection_explanation(
    request: Request, auth: AuthContext = Depends(require_observer)
) -> SuccessResponse[ServiceSelectionExplanation]:
    """
    Get service selection logic explanation.

    Returns detailed explanation of how services are selected, including
    priority groups, priorities, strategies, and circuit breaker behavior.
    """
    # Try main runtime control service first (has all methods), fall back to API runtime control
    runtime_control = getattr(request.app.state, "main_runtime_control_service", None)
    if not runtime_control:
        runtime_control = getattr(request.app.state, "runtime_control_service", None)
    if not runtime_control:
        raise HTTPException(status_code=503, detail=ERROR_RUNTIME_CONTROL_SERVICE_NOT_AVAILABLE)

    try:
        explanation = await runtime_control.get_service_selection_explanation()
        return SuccessResponse(data=explanation)
    except Exception as e:
        logger.error(f"Error getting service selection explanation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Processor State Information


class ProcessorStateInfo(BaseModel):
    """Information about a processor state."""

    name: str = Field(..., description="State name (WAKEUP, WORK, DREAM, etc.)")
    is_active: bool = Field(..., description="Whether this state is currently active")
    description: str = Field(..., description="State description")
    capabilities: List[str] = Field(default_factory=list, description="What this state can do")


@router.get("/processors", response_model=SuccessResponse[List[ProcessorStateInfo]])
async def get_processor_states(
    request: Request, auth: AuthContext = Depends(require_observer)
) -> SuccessResponse[List[ProcessorStateInfo]]:
    """
    Get information about all processor states.

    Returns the list of available processor states (WAKEUP, WORK, DREAM, PLAY,
    SOLITUDE, SHUTDOWN) and which one is currently active.
    """
    runtime = getattr(request.app.state, "runtime", None)
    if not runtime or not hasattr(runtime, "agent_processor"):
        raise HTTPException(status_code=503, detail="Agent processor not available")

    try:
        # Get current state from agent processor
        current_state = None
        if hasattr(runtime.agent_processor, "state_manager") and runtime.agent_processor.state_manager:
            current_state = runtime.agent_processor.state_manager.get_state()

        # Define all processor states with descriptions
        processor_states = [
            ProcessorStateInfo(
                name="WAKEUP",
                is_active=str(current_state) == "WAKEUP" if current_state else False,
                description="Initial state for identity confirmation and system initialization",
                capabilities=["identity_confirmation", "system_checks", "initial_setup"],
            ),
            ProcessorStateInfo(
                name="WORK",
                is_active=str(current_state) == "WORK" if current_state else False,
                description="Normal task processing and interaction state",
                capabilities=["task_processing", "user_interaction", "tool_usage", "memory_operations"],
            ),
            ProcessorStateInfo(
                name="DREAM",
                is_active=str(current_state) == "DREAM" if current_state else False,
                description="Deep introspection and memory consolidation state",
                capabilities=["memory_consolidation", "pattern_analysis", "self_reflection"],
            ),
            ProcessorStateInfo(
                name="PLAY",
                is_active=str(current_state) == "PLAY" if current_state else False,
                description="Creative exploration and experimentation state",
                capabilities=["creative_tasks", "exploration", "learning", "experimentation"],
            ),
            ProcessorStateInfo(
                name="SOLITUDE",
                is_active=str(current_state) == "SOLITUDE" if current_state else False,
                description="Quiet reflection and planning state",
                capabilities=["planning", "reflection", "goal_setting", "strategy_development"],
            ),
            ProcessorStateInfo(
                name="SHUTDOWN",
                is_active=str(current_state) == "SHUTDOWN" if current_state else False,
                description="Graceful shutdown and cleanup state",
                capabilities=["cleanup", "final_messages", "state_persistence", "resource_release"],
            ),
        ]

        return SuccessResponse(data=processor_states)

    except Exception as e:
        logger.error(f"Error getting processor states: {e}")
        raise HTTPException(status_code=500, detail=str(e))
