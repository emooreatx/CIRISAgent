"""
Visibility service endpoints for CIRIS API v1.

Deep introspection into agent reasoning and decision-making.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends, Query, WebSocket
from pydantic import BaseModel, Field
import json
import asyncio

from ciris_engine.schemas.api.responses import SuccessResponse, ErrorResponse, ErrorCode
from ciris_engine.schemas.services.visibility import (
    VisibilitySnapshot,
    ReasoningTrace,
    TaskDecisionHistory,
    ThoughtStep,
    DecisionRecord
)
from ciris_engine.schemas.runtime.models import Task, Thought
from ciris_engine.api.dependencies.auth import require_observer, require_admin, AuthContext

router = APIRouter(prefix="/visibility", tags=["visibility"])

# Request/Response schemas

class ReasoningResponse(BaseModel):
    """Current reasoning trace response."""
    current_task_id: Optional[str] = Field(None, description="ID of current task being processed")
    current_task_description: Optional[str] = Field(None, description="Description of current task")
    reasoning_trace: Optional[ReasoningTrace] = Field(None, description="Full reasoning trace if task active")
    reasoning_depth: int = Field(0, description="Current depth of reasoning chain")
    active_thought_count: int = Field(0, description="Number of active thoughts")

class ThoughtsResponse(BaseModel):
    """Recent thoughts response."""
    thoughts: List[Thought] = Field(..., description="Recent thoughts")
    total: int = Field(..., description="Total count")
    has_more: bool = Field(False, description="Whether more thoughts are available")

class DecisionsResponse(BaseModel):
    """Decision history response."""
    decisions: List[DecisionRecord] = Field(..., description="Recent decisions")
    total: int = Field(..., description="Total count")
    by_task: Dict[str, int] = Field(default_factory=dict, description="Decision count by task")

class StateResponse(BaseModel):
    """Cognitive state response."""
    snapshot: VisibilitySnapshot = Field(..., description="Current visibility snapshot")
    cognitive_state: str = Field(..., description="Current cognitive state")
    state_duration_seconds: float = Field(0.0, description="Time in current state")

class ExplanationsResponse(BaseModel):
    """Action explanations response."""
    explanations: List[Dict[str, Any]] = Field(..., description="Recent action explanations")
    total: int = Field(..., description="Total count")

class StreamMessage(BaseModel):
    """WebSocket stream message."""
    type: str = Field(..., description="Message type: reasoning|thought|decision|state")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: Dict[str, Any] = Field(..., description="Message data")

# Endpoints

@router.get("/reasoning", response_model=SuccessResponse[ReasoningResponse])
async def get_reasoning_trace(
    request: Request,
    task_id: Optional[str] = Query(None, description="Specific task ID to trace"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get current reasoning trace.
    
    Returns the current reasoning trace for the active task or a specific task.
    """
    visibility_service = getattr(request.app.state, 'visibility_service', None)
    if not visibility_service:
        raise HTTPException(status_code=503, detail="Visibility service not available")
    
    try:
        # Get current state
        snapshot = await visibility_service.get_current_state()
        
        response = ReasoningResponse(
            reasoning_depth=snapshot.reasoning_depth,
            active_thought_count=len(snapshot.active_thoughts)
        )
        
        # If specific task requested or current task exists
        target_task_id = task_id
        if not target_task_id and snapshot.current_task:
            target_task_id = snapshot.current_task.task_id
            response.current_task_id = target_task_id
            response.current_task_description = snapshot.current_task.description
        
        # Get reasoning trace if we have a task
        if target_task_id:
            try:
                trace = await visibility_service.get_reasoning_trace(target_task_id)
                response.reasoning_trace = trace
            except Exception as e:
                # Task might not exist or have no trace yet
                pass
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/thoughts", response_model=SuccessResponse[ThoughtsResponse])
async def get_recent_thoughts(
    request: Request,
    limit: int = Query(10, ge=1, le=100, description="Maximum thoughts to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get recent thoughts.
    
    Returns the agent's recent thoughts and reasoning steps.
    """
    visibility_service = getattr(request.app.state, 'visibility_service', None)
    if not visibility_service:
        raise HTTPException(status_code=503, detail="Visibility service not available")
    
    try:
        # Get current state
        snapshot = await visibility_service.get_current_state()
        
        # Combine active thoughts and recent decisions
        all_thoughts = snapshot.active_thoughts + snapshot.recent_decisions
        
        # Sort by timestamp (most recent first)
        all_thoughts.sort(key=lambda t: t.created_at, reverse=True)
        
        # Apply pagination
        total = len(all_thoughts)
        paginated = all_thoughts[offset:offset + limit]
        
        response = ThoughtsResponse(
            thoughts=paginated,
            total=total,
            has_more=(offset + limit) < total
        )
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/decisions", response_model=SuccessResponse[DecisionsResponse])
async def get_decision_history(
    request: Request,
    task_id: Optional[str] = Query(None, description="Filter by task ID"),
    limit: int = Query(10, ge=1, le=100, description="Maximum decisions to return"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get decision history.
    
    Returns the history of decisions made by the agent.
    """
    visibility_service = getattr(request.app.state, 'visibility_service', None)
    if not visibility_service:
        raise HTTPException(status_code=503, detail="Visibility service not available")
    
    try:
        decisions = []
        by_task = {}
        
        if task_id:
            # Get decisions for specific task
            try:
                history = await visibility_service.get_decision_history(task_id)
                decisions.extend(history.decisions[:limit])
                by_task[task_id] = len(history.decisions)
            except:
                pass
        else:
            # Get recent decisions from snapshot
            snapshot = await visibility_service.get_current_state()
            
            # Convert recent decision thoughts to DecisionRecord format
            for thought in snapshot.recent_decisions[:limit]:
                if thought.final_action:
                    record = DecisionRecord(
                        decision_id=thought.thought_id,
                        timestamp=datetime.fromisoformat(thought.created_at),
                        thought_id=thought.thought_id,
                        action_type=thought.final_action.action_type,
                        parameters=thought.final_action.action_params,
                        rationale=thought.content,
                        alternatives_considered=[],
                        executed=True,
                        result=None,
                        success=True
                    )
                    decisions.append(record)
                    
                    # Count by task
                    if thought.task_id:
                        by_task[thought.task_id] = by_task.get(thought.task_id, 0) + 1
        
        response = DecisionsResponse(
            decisions=decisions,
            total=len(decisions),
            by_task=by_task
        )
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/state", response_model=SuccessResponse[StateResponse])
async def get_cognitive_state(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get cognitive state.
    
    Returns the current cognitive state and visibility snapshot.
    """
    visibility_service = getattr(request.app.state, 'visibility_service', None)
    if not visibility_service:
        raise HTTPException(status_code=503, detail="Visibility service not available")
    
    try:
        # Get current state
        snapshot = await visibility_service.get_current_state()
        
        # Get cognitive state from runtime
        cognitive_state = "UNKNOWN"
        state_duration = 0.0
        
        runtime = getattr(request.app.state, 'runtime', None)
        if runtime:
            cognitive_state = runtime.cognitive_state.value
            # Calculate duration if we have state transition history
            # For now, we'll use a placeholder
            state_duration = 0.0
        
        response = StateResponse(
            snapshot=snapshot,
            cognitive_state=cognitive_state,
            state_duration_seconds=state_duration
        )
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/explanations", response_model=SuccessResponse[ExplanationsResponse])
async def get_action_explanations(
    request: Request,
    action_id: Optional[str] = Query(None, description="Specific action to explain"),
    limit: int = Query(10, ge=1, le=100, description="Maximum explanations to return"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get action explanations.
    
    Returns explanations for why specific actions were taken.
    """
    visibility_service = getattr(request.app.state, 'visibility_service', None)
    if not visibility_service:
        raise HTTPException(status_code=503, detail="Visibility service not available")
    
    try:
        explanations = []
        
        if action_id:
            # Get explanation for specific action
            try:
                explanation = await visibility_service.explain_action(action_id)
                explanations.append({
                    "action_id": action_id,
                    "explanation": explanation,
                    "timestamp": datetime.now(timezone.utc)
                })
            except Exception as e:
                raise HTTPException(status_code=404, detail=f"Action {action_id} not found")
        else:
            # Get recent action explanations from thoughts
            snapshot = await visibility_service.get_current_state()
            
            for thought in snapshot.recent_decisions[:limit]:
                if thought.final_action:
                    explanations.append({
                        "action_id": thought.thought_id,
                        "action_type": thought.final_action.action_type,
                        "parameters": thought.final_action.action_params,
                        "explanation": thought.content,
                        "timestamp": datetime.fromisoformat(thought.created_at)
                    })
        
        response = ExplanationsResponse(
            explanations=explanations,
            total=len(explanations)
        )
        
        return SuccessResponse(data=response)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/stream")
async def visibility_stream(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="API key for authentication")
):
    """
    Real-time reasoning stream.
    
    Stream visibility updates via WebSocket.
    """
    await websocket.accept()
    
    # Simple auth check
    if not token:
        await websocket.send_json({
            "type": "error",
            "data": {"message": "Authentication required"}
        })
        await websocket.close()
        return
    
    visibility_service = None
    try:
        visibility_service = websocket.app.state.visibility_service
    except:
        await websocket.send_json({
            "type": "error",
            "data": {"message": "Visibility service not available"}
        })
        await websocket.close()
        return
    
    try:
        # Send initial state
        snapshot = await visibility_service.get_current_state()
        await websocket.send_json({
            "type": "state",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "reasoning_depth": snapshot.reasoning_depth,
                "active_thoughts": len(snapshot.active_thoughts),
                "current_task": snapshot.current_task.task_id if snapshot.current_task else None
            }
        })
        
        # Stream updates
        while True:
            try:
                # Poll for updates every second
                await asyncio.sleep(1.0)
                
                # Get fresh snapshot
                new_snapshot = await visibility_service.get_current_state()
                
                # Send thought updates
                if new_snapshot.active_thoughts:
                    latest_thought = new_snapshot.active_thoughts[-1]
                    await websocket.send_json({
                        "type": "thought",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "data": {
                            "thought_id": latest_thought.thought_id,
                            "content": latest_thought.content,
                            "task_id": latest_thought.source_task_id
                        }
                    })
                
                # Send decision updates
                if new_snapshot.recent_decisions:
                    latest_decision = new_snapshot.recent_decisions[0]
                    if latest_decision.final_action:
                        await websocket.send_json({
                            "type": "decision",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "data": {
                                "decision_id": latest_decision.thought_id,
                                "action": latest_decision.final_action.action_type,
                                "parameters": latest_decision.final_action.action_params
                            }
                        })
                
                # Check for client messages
                try:
                    client_message = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                    # Handle client messages if needed (e.g., filters, subscriptions)
                    data = json.loads(client_message)
                    if data.get("type") == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                except asyncio.TimeoutError:
                    pass
                
            except Exception as e:
                # Log error but continue streaming
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": f"Stream error: {str(e)}"}
                })
                
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "data": {"message": f"Fatal error: {str(e)}"}
        })
    finally:
        await websocket.close()