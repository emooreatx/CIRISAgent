"""
Adaptive Filter Service endpoints for CIRIS API v1.

Manages the configurable message filtering system that prioritizes messages
and detects suspicious patterns across all adapters.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from ciris_engine.schemas.api.responses import SuccessResponse, ErrorResponse, ErrorCode
from ciris_engine.schemas.services.filters_core import (
    FilterTrigger, FilterResult, FilterStats, FilterHealth,
    AdaptiveFilterConfig, FilterPriority, TriggerType,
    PriorityStats, TriggerStats
)
from ciris_engine.api.dependencies.auth import require_observer, require_admin, AuthContext
from ciris_engine.protocols.services.governance.filter import AdaptiveFilterServiceProtocol

router = APIRouter(prefix="/filters", tags=["filters"])

# Request/Response schemas

class FilterTestRequest(BaseModel):
    """Request to test message filtering."""
    message: str = Field(..., description="Message content to test")
    adapter_type: str = Field("api", description="Adapter type (discord, cli, api)")
    is_llm_response: bool = Field(False, description="Whether this is an LLM-generated response")
    user_id: Optional[str] = Field(None, description="Optional user ID for context")
    channel_id: Optional[str] = Field(None, description="Optional channel ID for context")

class FilterRulesResponse(BaseModel):
    """Current filter rules organized by category."""
    attention_triggers: List[FilterTrigger] = Field(..., description="High-priority triggers")
    review_triggers: List[FilterTrigger] = Field(..., description="Suspicious pattern triggers")
    llm_filters: List[FilterTrigger] = Field(..., description="LLM output filters")
    total_active: int = Field(..., description="Total active filters")
    config_version: int = Field(..., description="Configuration version")

class FilterStatsResponse(BaseModel):
    """Detailed filter statistics."""
    total_messages_processed: int = Field(..., description="Total messages processed")
    total_filtered: int = Field(..., description="Messages filtered out")
    filter_rate: float = Field(..., description="Percentage of messages filtered")
    by_priority: List[PriorityStats] = Field(..., description="Breakdown by priority")
    by_trigger_type: List[TriggerStats] = Field(..., description="Breakdown by trigger type")
    false_positive_rate: float = Field(..., description="Estimated false positive rate")
    effectiveness_score: float = Field(..., description="Overall effectiveness score")
    last_reset: datetime = Field(..., description="When stats were last reset")

class FilterConfigUpdate(BaseModel):
    """Request to update filter configuration."""
    add_triggers: Optional[List[FilterTrigger]] = Field(None, description="Triggers to add")
    remove_trigger_ids: Optional[List[str]] = Field(None, description="Trigger IDs to remove")
    update_triggers: Optional[List[FilterTrigger]] = Field(None, description="Triggers to update")
    auto_adjust: Optional[bool] = Field(None, description="Enable/disable auto-adjustment")
    adjustment_interval: Optional[int] = Field(None, ge=60, description="Seconds between adjustments")
    effectiveness_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Min effectiveness")
    false_positive_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Max false positive rate")

class FilterEffectivenessResponse(BaseModel):
    """Filter performance metrics."""
    overall_effectiveness: float = Field(..., description="Overall effectiveness score (0-1)")
    precision: float = Field(..., description="True positive rate")
    recall: float = Field(..., description="Coverage of actual issues")
    top_performers: List[FilterTrigger] = Field(..., description="Most effective filters")
    underperformers: List[FilterTrigger] = Field(..., description="Least effective filters")
    recommendations: List[str] = Field(..., description="Improvement recommendations")

# Helper functions

def _get_filter_service(request: Request) -> AdaptiveFilterServiceProtocol:
    """Get adaptive filter service from app state."""
    filter_service = getattr(request.app.state, 'adaptive_filter_service', None)
    if not filter_service:
        raise HTTPException(status_code=503, detail="Adaptive filter service not available")
    return filter_service

def _calculate_stats_breakdown(stats: FilterStats) -> tuple[List[PriorityStats], List[TriggerStats]]:
    """Calculate percentage breakdowns for stats."""
    # Priority breakdown
    priority_stats = []
    total_by_priority = sum(stats.by_priority.values())
    for priority in FilterPriority:
        count = stats.by_priority.get(priority, 0)
        percentage = (count / total_by_priority * 100) if total_by_priority > 0 else 0.0
        priority_stats.append(PriorityStats(
            priority=priority,
            count=count,
            percentage=percentage
        ))
    
    # Trigger type breakdown
    trigger_stats = []
    total_by_trigger = sum(stats.by_trigger_type.values())
    for trigger_type in TriggerType:
        count = stats.by_trigger_type.get(trigger_type, 0)
        percentage = (count / total_by_trigger * 100) if total_by_trigger > 0 else 0.0
        trigger_stats.append(TriggerStats(
            trigger_type=trigger_type,
            count=count,
            percentage=percentage
        ))
    
    return priority_stats, trigger_stats

# Endpoints

@router.get("/rules", response_model=SuccessResponse[FilterRulesResponse])
async def get_filter_rules(
    request: Request,
    auth: AuthContext = Depends(require_observer),
    include_disabled: bool = Query(False, description="Include disabled filters")
):
    """
    Get current filter rules.
    
    Returns all active filter triggers organized by category.
    Optionally includes disabled filters for debugging.
    """
    filter_service = _get_filter_service(request)
    
    try:
        # Get health which includes the current config version
        health = filter_service.get_health()
        
        # For now, return empty config until memory service is properly set up
        # In a real deployment, this would query the memory service for the config
        config = AdaptiveFilterConfig()
        
        # Check if we can get config from filter service directly
        if hasattr(filter_service, 'get_config'):
            try:
                config = filter_service.get_config()
            except:
                pass
        
        
        # Filter out disabled triggers if requested
        if not include_disabled:
            attention_triggers = [t for t in config.attention_triggers if t.enabled]
            review_triggers = [t for t in config.review_triggers if t.enabled]
            llm_filters = [t for t in config.llm_filters if t.enabled]
        else:
            attention_triggers = config.attention_triggers
            review_triggers = config.review_triggers
            llm_filters = config.llm_filters
        
        total_active = len(attention_triggers) + len(review_triggers) + len(llm_filters)
        
        return SuccessResponse(data=FilterRulesResponse(
            attention_triggers=attention_triggers,
            review_triggers=review_triggers,
            llm_filters=llm_filters,
            total_active=total_active,
            config_version=config.version
        ))
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test", response_model=SuccessResponse[FilterResult])
async def test_filter(
    request: Request,
    body: FilterTestRequest,
    auth: AuthContext = Depends(require_observer)
):
    """
    Test message filtering.
    
    Applies current filter rules to a test message and returns the result.
    Useful for debugging filter behavior and tuning rules.
    """
    filter_service = _get_filter_service(request)
    
    try:
        # Create a mock message object with required fields
        test_message = {
            "content": body.message,
            "id": f"test_{datetime.now(timezone.utc).timestamp()}",
            "user_id": body.user_id or "test_user",
            "channel_id": body.channel_id or "test_channel"
        }
        
        result = await filter_service.filter_message(
            message=test_message,
            adapter_type=body.adapter_type,
            is_llm_response=body.is_llm_response
        )
        
        return SuccessResponse(data=result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats", response_model=SuccessResponse[FilterStatsResponse])
async def get_filter_stats(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get filter statistics.
    
    Returns detailed statistics about filter performance including
    message counts, trigger rates, and effectiveness metrics.
    """
    filter_service = _get_filter_service(request)
    
    try:
        health = filter_service.get_health()
        stats = health.stats
        
        # Calculate percentages and breakdowns
        priority_stats, trigger_stats = _calculate_stats_breakdown(stats)
        
        # Calculate overall metrics
        filter_rate = (stats.total_filtered / stats.total_messages_processed * 100) if stats.total_messages_processed > 0 else 0.0
        
        # Calculate false positive rate
        total_positives = stats.false_positive_reports + stats.true_positive_confirmations
        false_positive_rate = (stats.false_positive_reports / total_positives) if total_positives > 0 else 0.0
        
        # Calculate effectiveness score (simple formula: true positives / (true + false positives))
        effectiveness_score = (stats.true_positive_confirmations / total_positives) if total_positives > 0 else 0.5
        
        return SuccessResponse(data=FilterStatsResponse(
            total_messages_processed=stats.total_messages_processed,
            total_filtered=stats.total_filtered,
            filter_rate=filter_rate,
            by_priority=priority_stats,
            by_trigger_type=trigger_stats,
            false_positive_rate=false_positive_rate,
            effectiveness_score=effectiveness_score,
            last_reset=stats.last_reset
        ))
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/config", response_model=SuccessResponse[AdaptiveFilterConfig])
async def update_filter_config(
    request: Request,
    body: FilterConfigUpdate,
    auth: AuthContext = Depends(require_admin)
):
    """
    Update filter configuration.
    
    Requires ADMIN role. Allows adding, removing, or updating filter triggers
    and adjusting the adaptive learning parameters.
    """
    filter_service = _get_filter_service(request)
    
    try:
        # Get current config from filter service
        config = AdaptiveFilterConfig()
        if hasattr(filter_service, 'get_config'):
            try:
                config = filter_service.get_config()
            except:
                pass
        
        # Apply updates
        if body.add_triggers:
            for trigger in body.add_triggers:
                # Add to appropriate category based on priority
                if trigger.priority == FilterPriority.CRITICAL:
                    config.attention_triggers.append(trigger)
                elif trigger.priority in [FilterPriority.HIGH, FilterPriority.MEDIUM]:
                    config.review_triggers.append(trigger)
                # Note: LLM filters would need a different indicator
                
                # Also update service directly
                filter_service.add_filter_trigger(trigger)
        
        if body.remove_trigger_ids:
            for trigger_id in body.remove_trigger_ids:
                # Remove from all categories
                config.attention_triggers = [t for t in config.attention_triggers if t.trigger_id != trigger_id]
                config.review_triggers = [t for t in config.review_triggers if t.trigger_id != trigger_id]
                config.llm_filters = [t for t in config.llm_filters if t.trigger_id != trigger_id]
                
                # Also update service directly
                filter_service.remove_filter_trigger(trigger_id)
        
        if body.update_triggers:
            for updated_trigger in body.update_triggers:
                # Update in all categories
                for triggers in [config.attention_triggers, config.review_triggers, config.llm_filters]:
                    for i, trigger in enumerate(triggers):
                        if trigger.trigger_id == updated_trigger.trigger_id:
                            triggers[i] = updated_trigger
                            break
        
        # Update settings
        if body.auto_adjust is not None:
            config.auto_adjust = body.auto_adjust
        if body.adjustment_interval is not None:
            config.adjustment_interval = body.adjustment_interval
        if body.effectiveness_threshold is not None:
            config.effectiveness_threshold = body.effectiveness_threshold
        if body.false_positive_threshold is not None:
            config.false_positive_threshold = body.false_positive_threshold
        
        # Increment version
        config.version += 1
        config.last_adjustment = datetime.now(timezone.utc)
        
        # In a real deployment, this would store to memory service
        # For now, the filter service should handle its own config persistence
        
        return SuccessResponse(data=config)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/effectiveness", response_model=SuccessResponse[FilterEffectivenessResponse])
async def get_filter_effectiveness(
    request: Request,
    auth: AuthContext = Depends(require_observer),
    top_n: int = Query(5, ge=1, le=20, description="Number of top/bottom performers to return")
):
    """
    Get filter performance analysis.
    
    Returns detailed effectiveness metrics and recommendations for
    improving the filtering system based on observed performance.
    """
    filter_service = _get_filter_service(request)
    
    try:
        # Get current config and stats
        health = filter_service.get_health()
        stats = health.stats
        
        # Get filter config
        config = AdaptiveFilterConfig()
        if hasattr(filter_service, 'get_config'):
            try:
                config = filter_service.get_config()
            except:
                return SuccessResponse(data=FilterEffectivenessResponse(
                    overall_effectiveness=0.5,
                    precision=0.0,
                    recall=0.0,
                    top_performers=[],
                    underperformers=[],
                    recommendations=["No filter configuration found. Configure filters to begin analysis."]
                ))
        
        # Collect all triggers
        all_triggers = config.attention_triggers + config.review_triggers + config.llm_filters
        
        # Sort by effectiveness
        all_triggers.sort(key=lambda t: t.effectiveness * (1 - t.false_positive_rate), reverse=True)
        
        # Get top and bottom performers
        top_performers = all_triggers[:top_n] if len(all_triggers) >= top_n else all_triggers
        underperformers = all_triggers[-top_n:] if len(all_triggers) >= top_n else []
        
        # Calculate overall metrics
        total_positives = stats.false_positive_reports + stats.true_positive_confirmations
        precision = (stats.true_positive_confirmations / total_positives) if total_positives > 0 else 0.0
        
        # Estimate recall (this is harder without knowing total actual issues)
        # Use a heuristic based on trigger variety and coverage
        unique_trigger_types = len(set(t.pattern_type for t in all_triggers if t.enabled))
        recall = min(0.9, unique_trigger_types * 0.15)  # Rough estimate
        
        # F1 score as overall effectiveness
        overall_effectiveness = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        
        # Generate recommendations
        recommendations = []
        
        # Check for low effectiveness
        if overall_effectiveness < 0.5:
            recommendations.append("Overall effectiveness is low. Consider adding more diverse filter types.")
        
        # Check for high false positive rate
        high_fp_triggers = [t for t in all_triggers if t.false_positive_rate > config.false_positive_threshold]
        if high_fp_triggers:
            recommendations.append(f"Found {len(high_fp_triggers)} triggers with high false positive rates. Consider refining patterns.")
        
        # Check for low coverage
        if recall < 0.5:
            recommendations.append("Filter coverage appears low. Consider adding semantic filters for better context understanding.")
        
        # Check for disabled triggers
        disabled_count = sum(1 for t in all_triggers if not t.enabled)
        if disabled_count > len(all_triggers) * 0.3:
            recommendations.append(f"{disabled_count} filters are disabled. Review and remove obsolete filters.")
        
        # Check for old triggers
        stale_triggers = [t for t in all_triggers if t.last_triggered and 
                         (datetime.now(timezone.utc) - t.last_triggered).days > 30]
        if stale_triggers:
            recommendations.append(f"{len(stale_triggers)} filters haven't triggered in 30+ days. Consider removing stale patterns.")
        
        if not recommendations:
            recommendations.append("Filter system is performing well. Continue monitoring for optimization opportunities.")
        
        return SuccessResponse(data=FilterEffectivenessResponse(
            overall_effectiveness=overall_effectiveness,
            precision=precision,
            recall=recall,
            top_performers=top_performers,
            underperformers=underperformers,
            recommendations=recommendations
        ))
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health", response_model=SuccessResponse[FilterHealth])
async def get_filter_health(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get filter service health status.
    
    Returns the current health and operational status of the filtering system.
    """
    filter_service = _get_filter_service(request)
    
    try:
        health = filter_service.get_health()
        return SuccessResponse(data=health)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))