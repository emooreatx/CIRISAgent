"""
TSDB consolidation service endpoints for CIRIS API v1.

Manages time-series data consolidation for long-term memory.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.api.dependencies.auth import require_observer, require_admin, AuthContext
from ciris_engine.schemas.services.nodes import TSDBSummary
from ciris_engine.schemas.services.graph_core import NodeType, GraphScope
from ciris_engine.schemas.services.operations import MemoryQuery

router = APIRouter(prefix="/tsdb", tags=["tsdb"])

# Request/Response schemas

class TSDBSummaryAPI(BaseModel):
    """TSDB summary for API responses."""
    period_start: datetime = Field(..., description="Start of the consolidation period")
    period_end: datetime = Field(..., description="End of the consolidation period")
    period_label: str = Field(..., description="Human-readable period label")
    
    # Aggregated metrics
    total_tokens: int = Field(..., description="Total tokens used in period")
    total_cost_cents: float = Field(..., description="Total cost in cents")
    total_carbon_grams: float = Field(..., description="Total carbon emissions in grams")
    total_energy_kwh: float = Field(..., description="Total energy used in kWh")
    
    # Action summary
    action_counts: Dict[str, int] = Field(..., description="Count of each action type")
    error_count: int = Field(..., description="Total errors in period")
    success_rate: float = Field(..., description="Success rate (0-1)")
    
    # Metadata
    source_node_count: int = Field(..., description="Number of source nodes consolidated")
    consolidation_timestamp: datetime = Field(..., description="When consolidation occurred")
    
    @classmethod
    def from_tsdb_summary(cls, summary: TSDBSummary) -> 'TSDBSummaryAPI':
        """Convert from internal TSDBSummary to API model."""
        return cls(
            period_start=summary.period_start,
            period_end=summary.period_end,
            period_label=summary.period_label,
            total_tokens=summary.total_tokens,
            total_cost_cents=summary.total_cost_cents,
            total_carbon_grams=summary.total_carbon_grams,
            total_energy_kwh=summary.total_energy_kwh,
            action_counts=summary.action_counts,
            error_count=summary.error_count,
            success_rate=summary.success_rate,
            source_node_count=summary.source_node_count,
            consolidation_timestamp=summary.consolidation_timestamp
        )

class TSDBSummariesResponse(BaseModel):
    """Response containing multiple TSDB summaries."""
    summaries: List[TSDBSummaryAPI] = Field(..., description="List of TSDB summaries")
    total_count: int = Field(..., description="Total number of summaries found")
    query_start: datetime = Field(..., description="Start of query period")
    query_end: datetime = Field(..., description="End of query period")

class TSDBRetentionPolicy(BaseModel):
    """TSDB retention policy information."""
    raw_retention_hours: int = Field(..., description="Hours to retain raw TSDB nodes")
    consolidation_interval_hours: int = Field(..., description="Hours between consolidations")
    summary_retention: str = Field(..., description="Summary retention policy")
    next_consolidation: Optional[datetime] = Field(None, description="Next scheduled consolidation")
    last_consolidation: Optional[datetime] = Field(None, description="Last successful consolidation")

class ConsolidationRequest(BaseModel):
    """Request to manually trigger consolidation."""
    force_all: bool = Field(False, description="Force reconsolidation of all periods")
    period_start: Optional[datetime] = Field(None, description="Specific period to consolidate")

class ConsolidationResponse(BaseModel):
    """Response from manual consolidation."""
    status: str = Field(..., description="Consolidation status")
    message: str = Field(..., description="Status message")
    periods_processed: int = Field(0, description="Number of periods processed")

# Endpoints

@router.get("/summaries", response_model=SuccessResponse[TSDBSummariesResponse])
async def get_tsdb_summaries(
    request: Request,
    hours: int = Query(168, ge=1, le=8760, description="Hours of history to retrieve"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get consolidated TSDB summaries.
    
    Retrieve time-series data summaries for the specified time range.
    Summaries are created every 6 hours and contain aggregated metrics.
    """
    tsdb_service = getattr(request.app.state, 'tsdb_consolidation_service', None)
    if not tsdb_service:
        raise HTTPException(status_code=503, detail="TSDB consolidation service not available")
    
    try:
        # Calculate time range
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)
        
        # Get memory bus to query summaries
        memory_bus = getattr(tsdb_service, '_memory_bus', None)
        if not memory_bus:
            raise HTTPException(status_code=503, detail="Memory service not available")
        
        # Query for TSDB summaries in the time range
        query = MemoryQuery(
            node_id="tsdb_summary_*",  # Wildcard to get all TSDB summaries
            type=NodeType.TSDB_SUMMARY,
            scope=GraphScope.LOCAL,
            include_edges=False,
            depth=1
        )
        
        nodes = await memory_bus.recall(query, handler_name="tsdb_api")
        
        # Convert nodes to TSDBSummary objects
        summaries = []
        for node in nodes:
            if hasattr(TSDBSummary, 'from_graph_node'):
                try:
                    summary = TSDBSummary.from_graph_node(node)
                    # Filter by time range
                    if start_time <= summary.period_start <= end_time:
                        summaries.append(TSDBSummaryAPI.from_tsdb_summary(summary))
                except Exception as e:
                    logger.warning(f"Failed to convert node to TSDBSummary: {e}")
        
        # Sort by period start time
        summaries.sort(key=lambda s: s.period_start)
        
        response = TSDBSummariesResponse(
            summaries=summaries,
            total_count=len(summaries),
            query_start=start_time,
            query_end=end_time
        )
        
        return SuccessResponse(data=response)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/summaries/{period}", response_model=SuccessResponse[TSDBSummaryAPI])
async def get_summary_for_period(
    request: Request,
    period: str,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get specific period summary.
    
    Retrieve the TSDB summary for a specific 6-hour period.
    Period format: YYYYMMDD_HH (hour must be 00, 06, 12, or 18)
    
    Example: 20250627_12 for June 27, 2025 at 12:00 (noon period)
    """
    tsdb_service = getattr(request.app.state, 'tsdb_consolidation_service', None)
    if not tsdb_service:
        raise HTTPException(status_code=503, detail="TSDB consolidation service not available")
    
    try:
        # Parse period string
        if len(period) != 11 or period[8] != '_':
            raise HTTPException(
                status_code=400,
                detail="Invalid period format. Use YYYYMMDD_HH"
            )
        
        date_part = period[:8]
        hour_part = period[9:]
        
        # Validate hour is a valid consolidation period
        hour = int(hour_part)
        if hour not in [0, 6, 12, 18]:
            raise HTTPException(
                status_code=400,
                detail="Hour must be 00, 06, 12, or 18"
            )
        
        # Parse datetime
        period_start = datetime.strptime(f"{date_part} {hour_part}", "%Y%m%d %H")
        period_start = period_start.replace(tzinfo=timezone.utc)
        
        # Get summary for this period
        summary = await tsdb_service.get_summary_for_period(period_start)
        
        if not summary:
            raise HTTPException(
                status_code=404,
                detail=f"No summary found for period {period}"
            )
        
        return SuccessResponse(data=TSDBSummaryAPI.from_tsdb_summary(summary))
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid period format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/retention", response_model=SuccessResponse[TSDBRetentionPolicy])
async def get_retention_policy(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get retention policies.
    
    Get information about TSDB data retention and consolidation policies.
    """
    tsdb_service = getattr(request.app.state, 'tsdb_consolidation_service', None)
    if not tsdb_service:
        raise HTTPException(status_code=503, detail="TSDB consolidation service not available")
    
    try:
        # Get service capabilities for policy info
        capabilities = tsdb_service.get_capabilities()
        status = tsdb_service.get_status()
        
        # Extract policy information
        metadata = capabilities.metadata or {}
        metrics = status.metrics or {}
        
        # Calculate next consolidation time
        last_consolidation_ts = metrics.get("last_consolidation_timestamp", 0)
        last_consolidation = None
        next_consolidation = None
        
        if last_consolidation_ts > 0:
            last_consolidation = datetime.fromtimestamp(last_consolidation_ts, tz=timezone.utc)
            # Next consolidation is 6 hours after last
            next_consolidation = last_consolidation + timedelta(hours=6)
        
        policy = TSDBRetentionPolicy(
            raw_retention_hours=int(metadata.get("raw_retention_hours", 24)),
            consolidation_interval_hours=int(metadata.get("consolidation_interval_hours", 6)),
            summary_retention="permanent",  # Summaries are never deleted
            next_consolidation=next_consolidation,
            last_consolidation=last_consolidation
        )
        
        return SuccessResponse(data=policy)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/consolidate", response_model=SuccessResponse[ConsolidationResponse])
async def trigger_consolidation(
    request: Request,
    body: ConsolidationRequest,
    auth: AuthContext = Depends(require_admin)
):
    """
    Manual consolidation (ADMIN).
    
    Manually trigger TSDB consolidation. This is normally done automatically
    every 6 hours, but can be triggered manually for maintenance or recovery.
    
    Requires ADMIN role.
    """
    tsdb_service = getattr(request.app.state, 'tsdb_consolidation_service', None)
    if not tsdb_service:
        raise HTTPException(status_code=503, detail="TSDB consolidation service not available")
    
    try:
        if body.period_start:
            # Consolidate specific period
            # Validate period start is aligned to 6-hour boundary
            hour = body.period_start.hour
            if hour not in [0, 6, 12, 18]:
                raise HTTPException(
                    status_code=400,
                    detail="Period start hour must be 00, 06, 12, or 18"
                )
            
            # Use internal _force_consolidation method if available
            if hasattr(tsdb_service, '_force_consolidation'):
                summary = await tsdb_service._force_consolidation(body.period_start)
                if summary:
                    response = ConsolidationResponse(
                        status="success",
                        message=f"Successfully consolidated period {body.period_start}",
                        periods_processed=1
                    )
                else:
                    response = ConsolidationResponse(
                        status="no_data",
                        message=f"No data found for period {body.period_start}",
                        periods_processed=0
                    )
            else:
                raise HTTPException(
                    status_code=501,
                    detail="Manual consolidation not supported"
                )
        else:
            # Run normal consolidation cycle
            if hasattr(tsdb_service, '_run_consolidation'):
                await tsdb_service._run_consolidation()
                response = ConsolidationResponse(
                    status="success",
                    message="Consolidation cycle completed",
                    periods_processed=1  # We don't track exact count
                )
            else:
                raise HTTPException(
                    status_code=501,
                    detail="Manual consolidation not supported"
                )
        
        return SuccessResponse(data=response)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Add missing import
import logging
logger = logging.getLogger(__name__)