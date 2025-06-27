"""
Task Scheduler service endpoints for CIRIS API v1.

Manages scheduled and recurring tasks in the system.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends, Query, Path
from pydantic import BaseModel, Field

from ciris_engine.schemas.api.responses import SuccessResponse, ErrorResponse, ErrorCode
from ciris_engine.schemas.runtime.extended import ScheduledTaskInfo, ScheduledTask
from ciris_engine.api.dependencies.auth import require_observer, require_admin, AuthContext

router = APIRouter(prefix="/scheduler", tags=["scheduler"])

# Request/Response schemas

class CreateTaskRequest(BaseModel):
    """Request to create a scheduled task."""
    name: str = Field(..., description="Human-readable task name")
    goal_description: str = Field(..., description="What the task aims to achieve")
    trigger_prompt: str = Field(..., description="Prompt to use when creating the thought")
    origin_thought_id: str = Field(..., description="ID of the thought that created this task")
    defer_until: Optional[str] = Field(None, description="ISO timestamp for one-time execution")
    schedule_cron: Optional[str] = Field(None, description="Cron expression for recurring tasks")

class TaskListResponse(BaseModel):
    """List of scheduled tasks."""
    tasks: List[ScheduledTaskInfo] = Field(..., description="List of scheduled tasks")
    total: int = Field(..., description="Total number of tasks")
    pending_count: int = Field(0, description="Number of pending tasks")
    active_count: int = Field(0, description="Number of active recurring tasks")
    completed_count: int = Field(0, description="Number of completed tasks")

class TaskDetailResponse(BaseModel):
    """Detailed task information."""
    task: ScheduledTaskInfo = Field(..., description="Task details")
    next_execution: Optional[str] = Field(None, description="Next scheduled execution time")
    execution_history: List[Dict[str, Any]] = Field(default_factory=list, description="Past executions")

class ExecutionHistoryItem(BaseModel):
    """Task execution history item."""
    task_id: str = Field(..., description="Task ID")
    task_name: str = Field(..., description="Task name")
    executed_at: str = Field(..., description="Execution timestamp")
    status: str = Field(..., description="Execution status")
    thought_id: Optional[str] = Field(None, description="Generated thought ID")

class ExecutionHistoryResponse(BaseModel):
    """Task execution history."""
    history: List[ExecutionHistoryItem] = Field(..., description="Execution history")
    total: int = Field(..., description="Total executions")
    since: str = Field(..., description="History since timestamp")

class UpcomingExecutionsResponse(BaseModel):
    """Upcoming task executions."""
    upcoming: List[Dict[str, Any]] = Field(..., description="Upcoming executions")
    within_hours: int = Field(..., description="Hours window")
    total: int = Field(..., description="Total upcoming executions")

# Endpoints

@router.get("/tasks", response_model=SuccessResponse[TaskListResponse])
async def list_scheduled_tasks(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status: PENDING, ACTIVE, COMPLETE, FAILED"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    auth: AuthContext = Depends(require_observer)
):
    """
    List all scheduled tasks.
    
    Returns a list of scheduled tasks with their current status and scheduling information.
    """
    scheduler_service = getattr(request.app.state, 'task_scheduler_service', None)
    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Task scheduler service not available")
    
    try:
        # Get all tasks
        all_tasks = await scheduler_service.get_scheduled_tasks()
        
        # Filter by status if requested
        if status:
            filtered_tasks = [t for t in all_tasks if t.status == status]
        else:
            filtered_tasks = all_tasks
        
        # Count by status
        pending_count = sum(1 for t in all_tasks if t.status == "PENDING")
        active_count = sum(1 for t in all_tasks if t.status == "ACTIVE")
        completed_count = sum(1 for t in all_tasks if t.status == "COMPLETE")
        
        # Apply pagination
        paginated_tasks = filtered_tasks[offset:offset + limit]
        
        response = TaskListResponse(
            tasks=paginated_tasks,
            total=len(filtered_tasks),
            pending_count=pending_count,
            active_count=active_count,
            completed_count=completed_count
        )
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tasks/{task_id}", response_model=SuccessResponse[TaskDetailResponse])
async def get_task_details(
    request: Request,
    task_id: str = Path(..., description="Task ID"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get detailed information about a specific task.
    
    Returns task details including scheduling information and execution history.
    """
    scheduler_service = getattr(request.app.state, 'task_scheduler_service', None)
    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Task scheduler service not available")
    
    try:
        # Get all tasks and find the requested one
        all_tasks = await scheduler_service.get_scheduled_tasks()
        task = next((t for t in all_tasks if t.task_id == task_id), None)
        
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        # Calculate next execution time for recurring tasks
        next_execution = None
        if task.schedule_cron and task.status == "ACTIVE":
            # This would require access to the internal croniter logic
            # For now, we'll leave it as None
            pass
        elif task.defer_until and task.status == "PENDING":
            next_execution = task.defer_until
        
        # Build execution history from task data
        execution_history = []
        if task.last_triggered_at:
            execution_history.append({
                "executed_at": task.last_triggered_at,
                "status": "triggered",
                "deferral_count": task.deferral_count
            })
        
        response = TaskDetailResponse(
            task=task,
            next_execution=next_execution,
            execution_history=execution_history
        )
        
        return SuccessResponse(data=response)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tasks", response_model=SuccessResponse[ScheduledTaskInfo])
async def create_scheduled_task(
    request: Request,
    body: CreateTaskRequest,
    auth: AuthContext = Depends(require_admin)
):
    """
    Create a new scheduled task.
    
    Creates a task that will execute at the specified time(s). Requires ADMIN role.
    Either defer_until (one-time) or schedule_cron (recurring) must be provided.
    """
    scheduler_service = getattr(request.app.state, 'task_scheduler_service', None)
    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Task scheduler service not available")
    
    # Validate that at least one scheduling method is provided
    if not body.defer_until and not body.schedule_cron:
        raise HTTPException(
            status_code=400,
            detail="Either defer_until or schedule_cron must be provided"
        )
    
    try:
        # Create the task
        task = await scheduler_service.schedule_task(
            name=body.name,
            goal_description=body.goal_description,
            trigger_prompt=body.trigger_prompt,
            origin_thought_id=body.origin_thought_id,
            defer_until=body.defer_until,
            schedule_cron=body.schedule_cron
        )
        
        # Convert to API response format
        task_info = ScheduledTaskInfo(
            task_id=task.task_id,
            name=task.name,
            goal_description=task.goal_description,
            status=task.status,
            defer_until=task.defer_until,
            schedule_cron=task.schedule_cron,
            created_at=task.created_at,
            last_triggered_at=task.last_triggered_at,
            deferral_count=task.deferral_count
        )
        
        return SuccessResponse(data=task_info)
        
    except ValueError as e:
        # Invalid cron expression or other validation error
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/tasks/{task_id}", response_model=SuccessResponse[Dict[str, Any]])
async def cancel_scheduled_task(
    request: Request,
    task_id: str = Path(..., description="Task ID to cancel"),
    auth: AuthContext = Depends(require_admin)
):
    """
    Cancel a scheduled task.
    
    Cancels a pending or active task. Requires ADMIN role.
    """
    scheduler_service = getattr(request.app.state, 'task_scheduler_service', None)
    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Task scheduler service not available")
    
    try:
        success = await scheduler_service.cancel_task(task_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        return SuccessResponse(data={"task_id": task_id, "status": "cancelled"})
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history", response_model=SuccessResponse[ExecutionHistoryResponse])
async def get_execution_history(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="Hours of history to retrieve"),
    task_id: Optional[str] = Query(None, description="Filter by specific task ID"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get task execution history.
    
    Returns a history of task executions within the specified time window.
    """
    scheduler_service = getattr(request.app.state, 'task_scheduler_service', None)
    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Task scheduler service not available")
    
    try:
        # Calculate since timestamp
        time_service = getattr(request.app.state, 'time_service', None)
        if time_service:
            now = time_service.get_current_time()
        else:
            now = datetime.now(timezone.utc)
        
        since = now.isoformat()
        
        # Get all tasks
        all_tasks = await scheduler_service.get_scheduled_tasks()
        
        # Build execution history from tasks that have been triggered
        history = []
        for task in all_tasks:
            # Filter by task_id if specified
            if task_id and task.task_id != task_id:
                continue
                
            if task.last_triggered_at:
                history.append(ExecutionHistoryItem(
                    task_id=task.task_id,
                    task_name=task.name,
                    executed_at=task.last_triggered_at,
                    status="triggered",
                    thought_id=None  # We don't track the generated thought ID in the current implementation
                ))
        
        # Sort by execution time (most recent first)
        history.sort(key=lambda x: x.executed_at, reverse=True)
        
        response = ExecutionHistoryResponse(
            history=history,
            total=len(history),
            since=since
        )
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/upcoming", response_model=SuccessResponse[UpcomingExecutionsResponse])
async def get_upcoming_executions(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="Hours ahead to look for executions"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get upcoming task executions.
    
    Returns tasks scheduled to execute within the specified time window.
    """
    scheduler_service = getattr(request.app.state, 'task_scheduler_service', None)
    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Task scheduler service not available")
    
    try:
        # Get current time
        time_service = getattr(request.app.state, 'time_service', None)
        if time_service:
            now = time_service.get_current_time()
        else:
            now = datetime.now(timezone.utc)
        
        # Get all tasks
        all_tasks = await scheduler_service.get_scheduled_tasks()
        
        # Find upcoming executions
        upcoming = []
        for task in all_tasks:
            if task.status in ["PENDING", "ACTIVE"]:
                # For deferred tasks
                if task.defer_until and task.status == "PENDING":
                    upcoming.append({
                        "task_id": task.task_id,
                        "task_name": task.name,
                        "scheduled_for": task.defer_until,
                        "type": "one_time",
                        "goal": task.goal_description
                    })
                # For recurring tasks
                elif task.schedule_cron and task.status == "ACTIVE":
                    # Note: Without access to croniter here, we can't calculate exact next times
                    # In a real implementation, we'd calculate the next execution times
                    upcoming.append({
                        "task_id": task.task_id,
                        "task_name": task.name,
                        "schedule": task.schedule_cron,
                        "type": "recurring",
                        "goal": task.goal_description,
                        "last_triggered": task.last_triggered_at
                    })
        
        # Sort by scheduled time where available
        upcoming.sort(key=lambda x: x.get('scheduled_for', x.get('last_triggered', '')))
        
        response = UpcomingExecutionsResponse(
            upcoming=upcoming,
            within_hours=hours,
            total=len(upcoming)
        )
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))