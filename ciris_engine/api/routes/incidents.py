"""
Incident Management service endpoints for CIRIS API v1.

ITIL-aligned incident tracking and pattern detection for self-improvement.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.schemas.services.graph.incident import (
    IncidentNode, ProblemNode, IncidentInsightNode,
    IncidentSeverity, IncidentStatus
)
from ciris_engine.schemas.services.graph_core import GraphNode
from ciris_engine.api.dependencies.auth import require_observer, require_admin, AuthContext

router = APIRouter(prefix="/incidents", tags=["incidents"])

# Request/Response schemas

class IncidentSummary(BaseModel):
    """Summary view of an incident."""
    id: str = Field(..., description="Incident ID")
    incident_type: str = Field(..., description="Type of incident")
    severity: IncidentSeverity = Field(..., description="Incident severity")
    status: IncidentStatus = Field(..., description="Current status")
    description: str = Field(..., description="Incident description")
    source_component: str = Field(..., description="Component that generated the incident")
    detected_at: datetime = Field(..., description="When detected")
    resolved_at: Optional[datetime] = Field(None, description="When resolved")
    problem_id: Optional[str] = Field(None, description="Linked problem if recurring")

class ProblemSummary(BaseModel):
    """Summary view of a problem."""
    id: str = Field(..., description="Problem ID")
    problem_statement: str = Field(..., description="Problem description")
    status: str = Field(..., description="Problem status")
    incident_count: int = Field(..., description="Number of related incidents")
    first_occurrence: datetime = Field(..., description="First incident")
    last_occurrence: datetime = Field(..., description="Most recent incident")
    potential_root_causes: List[str] = Field(default_factory=list, description="Possible causes")
    recommended_actions: List[str] = Field(default_factory=list, description="Suggested fixes")

class PatternDetection(BaseModel):
    """Detected pattern in incidents."""
    pattern_type: str = Field(..., description="Type of pattern detected")
    description: str = Field(..., description="Pattern description")
    affected_components: List[str] = Field(..., description="Components involved")
    incident_count: int = Field(..., description="Number of incidents matching pattern")
    confidence: float = Field(..., ge=0, le=1, description="Detection confidence")
    time_window: str = Field(..., description="Time window of pattern")

class InsightSummary(BaseModel):
    """Summary view of an insight."""
    id: str = Field(..., description="Insight ID")
    insight_type: str = Field(..., description="Type of insight")
    summary: str = Field(..., description="High-level summary")
    behavioral_adjustments: List[str] = Field(default_factory=list, description="Behavioral changes")
    configuration_changes: List[str] = Field(default_factory=list, description="Config changes")
    analysis_timestamp: datetime = Field(..., description="When analyzed")
    applied: bool = Field(False, description="Whether applied")
    effectiveness_score: Optional[float] = Field(None, description="Effectiveness if applied")

class RecommendationCategory(BaseModel):
    """Category of recommendations."""
    category: str = Field(..., description="Category name")
    priority: str = Field(..., description="Priority level")
    recommendations: List[str] = Field(..., description="List of recommendations")
    rationale: str = Field(..., description="Why these are recommended")

class AnalyzeRequest(BaseModel):
    """Request to trigger incident analysis."""
    hours: int = Field(24, ge=1, le=168, description="Hours of history to analyze")
    force: bool = Field(False, description="Force re-analysis even if recent")

# Response models

class IncidentListResponse(BaseModel):
    """List of incidents."""
    incidents: List[IncidentSummary] = Field(..., description="Recent incidents")
    total: int = Field(..., description="Total count")
    severity_counts: Dict[str, int] = Field(..., description="Count by severity")
    status_counts: Dict[str, int] = Field(..., description="Count by status")

class PatternListResponse(BaseModel):
    """List of detected patterns."""
    patterns: List[PatternDetection] = Field(..., description="Detected patterns")
    total: int = Field(..., description="Total patterns found")
    analysis_period: str = Field(..., description="Period analyzed")

class ProblemListResponse(BaseModel):
    """List of problems."""
    problems: List[ProblemSummary] = Field(..., description="Current problems")
    total: int = Field(..., description="Total count")
    unresolved_count: int = Field(..., description="Unresolved problems")

class InsightListResponse(BaseModel):
    """List of insights."""
    insights: List[InsightSummary] = Field(..., description="Generated insights")
    total: int = Field(..., description="Total count")
    applied_count: int = Field(..., description="Applied insights")
    effectiveness_avg: Optional[float] = Field(None, description="Average effectiveness")

class RecommendationResponse(BaseModel):
    """Improvement recommendations."""
    recommendations: List[RecommendationCategory] = Field(..., description="Categorized recommendations")
    total_count: int = Field(..., description="Total recommendations")
    based_on_incidents: int = Field(..., description="Number of incidents analyzed")
    based_on_patterns: int = Field(..., description="Number of patterns considered")

# Endpoints

@router.get("", response_model=SuccessResponse[IncidentListResponse])
async def get_recent_incidents(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="Hours of history"),
    severity: Optional[IncidentSeverity] = Query(None, description="Filter by severity"),
    status: Optional[IncidentStatus] = Query(None, description="Filter by status"),
    component: Optional[str] = Query(None, description="Filter by component"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get recent incidents from the system.
    
    Returns incidents captured from logs with filtering options.
    """
    incident_service = getattr(request.app.state, 'incident_management_service', None)
    if not incident_service:
        raise HTTPException(status_code=503, detail="Incident management service not available")
    
    try:
        # Get memory service to query incidents
        memory_service = getattr(request.app.state, 'memory_service', None)
        if not memory_service:
            raise HTTPException(status_code=503, detail="Memory service not available")
        
        # Query incidents from graph
        # This is a simplified implementation - real one would use proper graph queries
        incidents = []
        severity_counts = {}
        status_counts = {}
        
        # TODO: Implement actual graph query for incidents
        # For now, return empty response
        
        return SuccessResponse(data=IncidentListResponse(
            incidents=incidents,
            total=len(incidents),
            severity_counts=severity_counts,
            status_counts=status_counts
        ))
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{incident_id}", response_model=SuccessResponse[IncidentNode])
async def get_incident_details(
    request: Request,
    incident_id: str,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get detailed information about a specific incident.
    
    Returns the full incident node from the graph.
    """
    memory_service = getattr(request.app.state, 'memory_service', None)
    if not memory_service:
        raise HTTPException(status_code=503, detail="Memory service not available")
    
    try:
        # Query specific incident from graph
        node = await memory_service.recall_one(f"incident:{incident_id}")
        if not node:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        # Convert to IncidentNode if it's a GraphNode
        if isinstance(node, GraphNode):
            incident = IncidentNode.from_graph_node(node)
        else:
            incident = node
            
        return SuccessResponse(data=incident)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/patterns", response_model=SuccessResponse[PatternListResponse])
async def get_incident_patterns(
    request: Request,
    hours: int = Query(168, ge=1, le=720, description="Hours of history to analyze"),
    min_incidents: int = Query(3, ge=2, description="Minimum incidents for pattern"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get detected patterns in incidents.
    
    Analyzes recent incidents to identify recurring patterns and trends.
    """
    incident_service = getattr(request.app.state, 'incident_management_service', None)
    if not incident_service:
        raise HTTPException(status_code=503, detail="Incident management service not available")
    
    try:
        # TODO: Implement pattern detection logic
        # For now, return empty response
        patterns = []
        
        return SuccessResponse(data=PatternListResponse(
            patterns=patterns,
            total=len(patterns),
            analysis_period=f"Last {hours} hours"
        ))
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/problems", response_model=SuccessResponse[ProblemListResponse])
async def get_current_problems(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status"),
    min_incidents: int = Query(2, ge=1, description="Minimum related incidents"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get current problems (root causes) identified from incidents.
    
    Problems are recurring issues that need systematic resolution.
    """
    memory_service = getattr(request.app.state, 'memory_service', None)
    if not memory_service:
        raise HTTPException(status_code=503, detail="Memory service not available")
    
    try:
        # TODO: Query problems from graph
        problems = []
        unresolved_count = 0
        
        return SuccessResponse(data=ProblemListResponse(
            problems=problems,
            total=len(problems),
            unresolved_count=unresolved_count
        ))
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/insights", response_model=SuccessResponse[InsightListResponse])
async def get_incident_insights(
    request: Request,
    days: int = Query(7, ge=1, le=30, description="Days of insights"),
    applied_only: bool = Query(False, description="Only show applied insights"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get insights generated from incident analysis.
    
    Insights contain recommendations for improving system behavior.
    """
    memory_service = getattr(request.app.state, 'memory_service', None)
    if not memory_service:
        raise HTTPException(status_code=503, detail="Memory service not available")
    
    try:
        # TODO: Query insights from graph
        insights = []
        applied_count = 0
        effectiveness_sum = 0.0
        effectiveness_count = 0
        
        effectiveness_avg = effectiveness_sum / effectiveness_count if effectiveness_count > 0 else None
        
        return SuccessResponse(data=InsightListResponse(
            insights=insights,
            total=len(insights),
            applied_count=applied_count,
            effectiveness_avg=effectiveness_avg
        ))
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze", response_model=SuccessResponse[IncidentInsightNode])
async def analyze_incidents(
    request: Request,
    body: AnalyzeRequest,
    auth: AuthContext = Depends(require_admin)
):
    """
    Trigger incident analysis to generate new insights.
    
    Requires ADMIN role as this can be resource-intensive.
    """
    incident_service = getattr(request.app.state, 'incident_management_service', None)
    if not incident_service:
        raise HTTPException(status_code=503, detail="Incident management service not available")
    
    try:
        # Check if recent analysis exists (unless forced)
        if not body.force:
            # TODO: Check for recent analysis in graph
            pass
        
        # Trigger analysis
        insight = await incident_service.process_recent_incidents(hours=body.hours)
        
        return SuccessResponse(data=insight)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recommendations", response_model=SuccessResponse[RecommendationResponse])
async def get_improvement_recommendations(
    request: Request,
    priority: Optional[str] = Query(None, description="Filter by priority"),
    category: Optional[str] = Query(None, description="Filter by category"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get actionable recommendations for system improvement.
    
    Aggregates recommendations from recent insights and patterns.
    """
    incident_service = getattr(request.app.state, 'incident_management_service', None)
    if not incident_service:
        raise HTTPException(status_code=503, detail="Incident management service not available")
    
    try:
        # TODO: Aggregate recommendations from insights
        recommendations = []
        total_count = 0
        based_on_incidents = 0
        based_on_patterns = 0
        
        # Example structure (would be populated from actual data)
        if not recommendations:  # Default example
            recommendations = [
                RecommendationCategory(
                    category="Error Handling",
                    priority="HIGH",
                    recommendations=[
                        "Implement retry logic for transient failures",
                        "Add circuit breakers for external service calls"
                    ],
                    rationale="Reduce cascading failures and improve resilience"
                ),
                RecommendationCategory(
                    category="Performance",
                    priority="MEDIUM",
                    recommendations=[
                        "Cache frequently accessed graph queries",
                        "Batch memory operations where possible"
                    ],
                    rationale="Optimize resource usage and response times"
                )
            ]
            total_count = 4
        
        return SuccessResponse(data=RecommendationResponse(
            recommendations=recommendations,
            total_count=total_count,
            based_on_incidents=based_on_incidents,
            based_on_patterns=based_on_patterns
        ))
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))