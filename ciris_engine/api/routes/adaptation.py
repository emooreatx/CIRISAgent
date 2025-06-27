"""
Self-Configuration Service endpoints for CIRIS API v1.

Provides visibility into autonomous adaptation patterns and insights.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.api.dependencies.auth import require_observer, AuthContext
from ciris_engine.schemas.infrastructure.feedback_loop import (
    DetectedPattern, AnalysisResult, PatternType, PatternMetrics
)
from ciris_engine.schemas.infrastructure.behavioral_patterns import (
    ActionFrequency, TemporalPattern
)

router = APIRouter(prefix="/adaptation", tags=["adaptation"])

# Response schemas

class PatternsList(BaseModel):
    """List of detected patterns."""
    patterns: List[DetectedPattern] = Field(..., description="Detected behavioral patterns")
    total: int = Field(..., description="Total patterns found")
    time_window_hours: int = Field(..., description="Analysis time window")

class PatternInsight(BaseModel):
    """A pattern-based insight stored in graph memory."""
    insight_id: str = Field(..., description="Unique insight identifier")
    pattern_id: str = Field(..., description="Source pattern ID")
    insight_type: str = Field(..., description="Type of insight")
    description: str = Field(..., description="Human-readable insight")
    confidence: float = Field(..., description="Confidence level (0.0-1.0)")
    created_at: datetime = Field(..., description="When insight was created")
    evidence_count: int = Field(..., description="Number of supporting evidence nodes")

class InsightsList(BaseModel):
    """List of pattern insights."""
    insights: List[PatternInsight] = Field(..., description="Pattern-based insights")
    total: int = Field(..., description="Total insights")

class AdaptationEvent(BaseModel):
    """A single adaptation event."""
    event_id: str = Field(..., description="Event identifier")
    timestamp: datetime = Field(..., description="When adaptation occurred")
    event_type: str = Field(..., description="Type of adaptation")
    description: str = Field(..., description="What was adapted")
    trigger_pattern: Optional[str] = Field(None, description="Pattern that triggered adaptation")
    effectiveness: Optional[float] = Field(None, description="Measured effectiveness")

class AdaptationHistory(BaseModel):
    """History of adaptations."""
    events: List[AdaptationEvent] = Field(..., description="Adaptation events")
    total: int = Field(..., description="Total adaptations")
    time_range_hours: int = Field(..., description="History time range")

class EffectivenessMetric(BaseModel):
    """Effectiveness measurement for a pattern or adaptation."""
    metric_name: str = Field(..., description="What is being measured")
    baseline_value: float = Field(..., description="Value before adaptation")
    current_value: float = Field(..., description="Value after adaptation")
    improvement_percentage: float = Field(..., description="Percentage improvement")
    confidence: float = Field(..., description="Confidence in measurement")
    samples: int = Field(..., description="Number of samples")

class EffectivenessReport(BaseModel):
    """Overall effectiveness metrics."""
    overall_effectiveness: float = Field(..., description="Overall effectiveness score (0.0-1.0)")
    metrics: List[EffectivenessMetric] = Field(..., description="Individual metrics")
    successful_patterns: int = Field(..., description="Patterns that improved outcomes")
    total_patterns: int = Field(..., description="Total patterns evaluated")
    evaluation_period_hours: int = Field(..., description="Evaluation time period")

class PatternCorrelation(BaseModel):
    """Correlation between patterns."""
    pattern_a: str = Field(..., description="First pattern ID")
    pattern_b: str = Field(..., description="Second pattern ID")
    correlation_score: float = Field(..., description="Correlation strength (-1.0 to 1.0)")
    correlation_type: str = Field(..., description="Type: positive, negative, temporal")
    confidence: float = Field(..., description="Confidence in correlation")
    evidence_count: int = Field(..., description="Supporting evidence count")

class CorrelationsList(BaseModel):
    """List of pattern correlations."""
    correlations: List[PatternCorrelation] = Field(..., description="Pattern correlations")
    total: int = Field(..., description="Total correlations found")
    min_confidence: float = Field(..., description="Minimum confidence threshold used")

class ImprovementReport(BaseModel):
    """Comprehensive improvement report."""
    report_timestamp: datetime = Field(..., description="Report generation time")
    summary: str = Field(..., description="Executive summary")
    detected_patterns: int = Field(..., description="Total patterns detected")
    active_adaptations: int = Field(..., description="Currently active adaptations")
    effectiveness_score: float = Field(..., description="Overall effectiveness (0.0-1.0)")
    top_improvements: List[str] = Field(..., description="Most effective improvements")
    recommendations: List[str] = Field(..., description="Future improvement recommendations")
    learning_insights: List[str] = Field(..., description="Key learnings from adaptations")

# Endpoints

@router.get("/patterns", response_model=SuccessResponse[PatternsList])
async def get_patterns(
    request: Request,
    pattern_type: Optional[PatternType] = Query(None, description="Filter by pattern type"),
    hours: int = Query(24, description="Look back period in hours", ge=1, le=168),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get detected behavioral patterns.
    
    Returns patterns detected by the self-configuration service,
    filtered by type and time window.
    """
    self_config_service = getattr(request.app.state, 'self_configuration_service', None)
    if not self_config_service:
        raise HTTPException(status_code=503, detail="Self-configuration service not available")
    
    try:
        # Get patterns from service
        patterns = await self_config_service.get_detected_patterns(
            pattern_type=pattern_type,
            hours=hours
        )
        
        result = PatternsList(
            patterns=patterns,
            total=len(patterns),
            time_window_hours=hours
        )
        
        return SuccessResponse(data=result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/insights", response_model=SuccessResponse[InsightsList])
async def get_insights(
    request: Request,
    limit: int = Query(50, description="Maximum insights to return", ge=1, le=200),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get pattern-based insights.
    
    Returns insights stored in graph memory that the agent uses
    for its reasoning and adaptation.
    """
    self_config_service = getattr(request.app.state, 'self_configuration_service', None)
    if not self_config_service:
        raise HTTPException(status_code=503, detail="Self-configuration service not available")
    
    try:
        # Get insights from service
        insight_nodes = await self_config_service.get_pattern_insights(limit=limit)
        
        # Convert to response format
        insights = []
        for node in insight_nodes:
            insight = PatternInsight(
                insight_id=node.get('id', ''),
                pattern_id=node.get('pattern_id', ''),
                insight_type=node.get('insight_type', 'general'),
                description=node.get('description', ''),
                confidence=node.get('confidence', 0.5),
                created_at=node.get('created_at', datetime.now(timezone.utc)),
                evidence_count=len(node.get('evidence_nodes', []))
            )
            insights.append(insight)
        
        result = InsightsList(
            insights=insights,
            total=len(insights)
        )
        
        return SuccessResponse(data=result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history", response_model=SuccessResponse[AdaptationHistory])
async def get_adaptation_history(
    request: Request,
    hours: int = Query(48, description="History period in hours", ge=1, le=720),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get adaptation history.
    
    Returns the history of autonomous adaptations made by the agent.
    """
    self_config_service = getattr(request.app.state, 'self_configuration_service', None)
    if not self_config_service:
        raise HTTPException(status_code=503, detail="Self-configuration service not available")
    
    try:
        # Get learning summary which includes adaptation history
        summary = await self_config_service.get_learning_summary()
        
        # Extract adaptation events
        events = []
        adaptations = summary.get('adaptations', [])
        
        for idx, adaptation in enumerate(adaptations):
            event = AdaptationEvent(
                event_id=f"adapt_{idx}",
                timestamp=adaptation.get('timestamp', datetime.now(timezone.utc)),
                event_type=adaptation.get('type', 'behavioral'),
                description=adaptation.get('description', ''),
                trigger_pattern=adaptation.get('trigger_pattern'),
                effectiveness=adaptation.get('effectiveness')
            )
            events.append(event)
        
        # Filter by time window
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        events = [e for e in events if e.timestamp >= cutoff_time]
        
        result = AdaptationHistory(
            events=events,
            total=len(events),
            time_range_hours=hours
        )
        
        return SuccessResponse(data=result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/effectiveness", response_model=SuccessResponse[EffectivenessReport])
async def get_effectiveness(
    request: Request,
    hours: int = Query(168, description="Evaluation period in hours", ge=24, le=720),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get effectiveness metrics.
    
    Returns metrics showing how effective the autonomous adaptations have been.
    """
    self_config_service = getattr(request.app.state, 'self_configuration_service', None)
    if not self_config_service:
        raise HTTPException(status_code=503, detail="Self-configuration service not available")
    
    try:
        # Get patterns to evaluate
        patterns = await self_config_service.get_detected_patterns(hours=hours)
        
        # Collect effectiveness metrics
        metrics = []
        successful_patterns = 0
        
        for pattern in patterns:
            effectiveness_data = await self_config_service.get_pattern_effectiveness(
                pattern_id=pattern.pattern_id
            )
            
            if effectiveness_data:
                # Calculate improvement
                baseline = effectiveness_data.get('baseline_value', 0)
                current = effectiveness_data.get('current_value', baseline)
                improvement = ((current - baseline) / baseline * 100) if baseline > 0 else 0
                
                if improvement > 0:
                    successful_patterns += 1
                
                metric = EffectivenessMetric(
                    metric_name=effectiveness_data.get('metric_name', pattern.description),
                    baseline_value=baseline,
                    current_value=current,
                    improvement_percentage=improvement,
                    confidence=effectiveness_data.get('confidence', 0.5),
                    samples=effectiveness_data.get('samples', 1)
                )
                metrics.append(metric)
        
        # Calculate overall effectiveness
        overall_effectiveness = successful_patterns / len(patterns) if patterns else 0
        
        result = EffectivenessReport(
            overall_effectiveness=overall_effectiveness,
            metrics=metrics,
            successful_patterns=successful_patterns,
            total_patterns=len(patterns),
            evaluation_period_hours=hours
        )
        
        return SuccessResponse(data=result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/correlations", response_model=SuccessResponse[CorrelationsList])
async def get_correlations(
    request: Request,
    min_confidence: float = Query(0.5, description="Minimum confidence threshold", ge=0.0, le=1.0),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get pattern correlations.
    
    Returns correlations between different behavioral patterns.
    """
    self_config_service = getattr(request.app.state, 'self_configuration_service', None)
    if not self_config_service:
        raise HTTPException(status_code=503, detail="Self-configuration service not available")
    
    try:
        # Get temporal patterns for correlation analysis
        temporal_patterns = await self_config_service.get_temporal_patterns()
        
        # Analyze correlations (simplified example)
        correlations = []
        
        # Look for patterns that occur together
        for i, pattern_a in enumerate(temporal_patterns):
            for pattern_b in temporal_patterns[i+1:]:
                # Check if patterns overlap in time
                if pattern_a.time_window == pattern_b.time_window:
                    correlation = PatternCorrelation(
                        pattern_a=pattern_a.pattern_id,
                        pattern_b=pattern_b.pattern_id,
                        correlation_score=0.8,  # Simplified
                        correlation_type="temporal",
                        confidence=0.7,
                        evidence_count=min(pattern_a.occurrence_count, pattern_b.occurrence_count)
                    )
                    if correlation.confidence >= min_confidence:
                        correlations.append(correlation)
        
        result = CorrelationsList(
            correlations=correlations,
            total=len(correlations),
            min_confidence=min_confidence
        )
        
        return SuccessResponse(data=result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/report", response_model=SuccessResponse[ImprovementReport])
async def get_improvement_report(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get improvement report.
    
    Returns a comprehensive report on the agent's self-improvement
    through autonomous adaptation.
    """
    self_config_service = getattr(request.app.state, 'self_configuration_service', None)
    if not self_config_service:
        raise HTTPException(status_code=503, detail="Self-configuration service not available")
    
    try:
        # Get analysis status
        status = await self_config_service.get_analysis_status()
        
        # Get learning summary
        summary = await self_config_service.get_learning_summary()
        
        # Get recent patterns
        patterns = await self_config_service.get_detected_patterns(hours=168)
        
        # Calculate effectiveness
        successful_patterns = 0
        for pattern in patterns:
            effectiveness = await self_config_service.get_pattern_effectiveness(pattern.pattern_id)
            if effectiveness and effectiveness.get('improvement', 0) > 0:
                successful_patterns += 1
        
        effectiveness_score = successful_patterns / len(patterns) if patterns else 0
        
        # Build report
        report = ImprovementReport(
            report_timestamp=datetime.now(timezone.utc),
            summary=f"The agent has detected {len(patterns)} behavioral patterns and made {status.get('total_adaptations', 0)} adaptations with {effectiveness_score:.1%} effectiveness.",
            detected_patterns=len(patterns),
            active_adaptations=status.get('active_adaptations', 0),
            effectiveness_score=effectiveness_score,
            top_improvements=summary.get('top_improvements', []),
            recommendations=summary.get('recommendations', []),
            learning_insights=summary.get('insights', [])
        )
        
        return SuccessResponse(data=report)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))