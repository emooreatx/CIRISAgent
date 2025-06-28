"""
Audit service endpoints for CIRIS API v1.

Provides access to the immutable audit trail for system observability.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends, Query, Path
from pydantic import BaseModel, Field, field_serializer

from ciris_engine.schemas.api.responses import SuccessResponse, ErrorResponse, ErrorCode
from ciris_engine.schemas.services.nodes import AuditEntry
from ciris_engine.schemas.services.graph.audit import AuditQuery, VerificationReport
from ciris_engine.api.dependencies.auth import require_observer, require_admin, AuthContext
from ciris_engine.protocols.services.graph.audit import AuditServiceProtocol

router = APIRouter(prefix="/audit", tags=["audit"])

# Response schemas specific to API

class AuditEntryResponse(BaseModel):
    """Audit entry response with formatted fields."""
    id: str = Field(..., description="Audit entry ID")
    action: str = Field(..., description="Action performed")
    actor: str = Field(..., description="Who performed the action")
    timestamp: datetime = Field(..., description="When action occurred")
    context: Dict[str, Any] = Field(..., description="Action context")
    signature: Optional[str] = Field(None, description="Cryptographic signature")
    hash_chain: Optional[str] = Field(None, description="Previous hash for chain")
    
    @field_serializer('timestamp')
    def serialize_timestamp(self, timestamp: datetime, _info):
        return timestamp.isoformat() if timestamp else None

class AuditEntriesResponse(BaseModel):
    """List of audit entries."""
    entries: List[AuditEntryResponse] = Field(..., description="Audit entries")
    total: int = Field(..., description="Total matching entries")
    offset: int = Field(0, description="Results offset")
    limit: int = Field(100, description="Results limit")

class AuditExportResponse(BaseModel):
    """Audit export response."""
    format: str = Field(..., description="Export format")
    total_entries: int = Field(..., description="Total entries exported")
    export_url: Optional[str] = Field(None, description="URL to download export")
    export_data: Optional[str] = Field(None, description="Inline export data for small exports")

# Helper functions

def _convert_audit_entry(entry: AuditEntry) -> AuditEntryResponse:
    """Convert AuditEntry to API response format."""
    return AuditEntryResponse(
        id=getattr(entry, 'id', f"audit_{entry.timestamp.isoformat()}"),
        action=entry.action,
        actor=entry.actor,
        timestamp=entry.timestamp,
        context=entry.context.model_dump() if hasattr(entry.context, 'model_dump') else {},
        signature=entry.signature,
        hash_chain=entry.hash_chain
    )

async def _get_audit_service(request: Request) -> AuditServiceProtocol:
    """Get audit service from app state."""
    audit_service = getattr(request.app.state, 'audit_service', None)
    if not audit_service:
        raise HTTPException(status_code=503, detail="Audit service not available")
    return audit_service

# Endpoints

@router.get("/entries", response_model=SuccessResponse[AuditEntriesResponse])
async def get_audit_entries(
    request: Request,
    auth: AuthContext = Depends(require_observer),
    start_time: Optional[datetime] = Query(None, description="Start of time range"),
    end_time: Optional[datetime] = Query(None, description="End of time range"),
    actor: Optional[str] = Query(None, description="Filter by actor"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results offset")
):
    """
    Query audit log entries.
    
    Returns paginated list of audit entries matching the query parameters.
    Requires OBSERVER role or higher.
    """
    audit_service = await _get_audit_service(request)
    
    # Build query
    query = AuditQuery(
        start_time=start_time,
        end_time=end_time,
        actor=actor,
        event_type=event_type,
        limit=limit,
        offset=offset,
        order_by="timestamp",
        order_desc=True
    )
    
    try:
        entries = await audit_service.query_audit_trail(query)
        
        # Convert to response format
        response_entries = [_convert_audit_entry(entry) for entry in entries]
        
        return SuccessResponse(data=AuditEntriesResponse(
            entries=response_entries,
            total=len(entries),  # Note: In real implementation, would get total from service
            offset=offset,
            limit=limit
        ))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/entries/{entry_id}", response_model=SuccessResponse[AuditEntryResponse])
async def get_audit_entry(
    request: Request,
    entry_id: str = Path(..., description="Audit entry ID"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get specific audit entry by ID.
    
    Requires OBSERVER role or higher.
    """
    audit_service = await _get_audit_service(request)
    
    try:
        # Try to get by ID using query
        query = AuditQuery(
            search_text=entry_id,  # Search in details
            limit=1
        )
        entries = await audit_service.query_audit_trail(query)
        
        if not entries:
            raise HTTPException(status_code=404, detail="Audit entry not found")
        
        return SuccessResponse(data=_convert_audit_entry(entries[0]))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search", response_model=SuccessResponse[AuditEntriesResponse])
async def search_audit_trails(
    request: Request,
    auth: AuthContext = Depends(require_observer),
    search_text: str = Query(..., description="Text to search for"),
    entity_id: Optional[str] = Query(None, description="Filter by entity ID"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    outcome: Optional[str] = Query(None, description="Filter by outcome"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results offset")
):
    """
    Search audit trails with text search and filters.
    
    Requires OBSERVER role or higher.
    """
    audit_service = await _get_audit_service(request)
    
    # Build query
    query = AuditQuery(
        search_text=search_text,
        entity_id=entity_id,
        severity=severity,
        outcome=outcome,
        limit=limit,
        offset=offset,
        order_by="timestamp",
        order_desc=True
    )
    
    try:
        entries = await audit_service.query_audit_trail(query)
        
        # Convert to response format
        response_entries = [_convert_audit_entry(entry) for entry in entries]
        
        return SuccessResponse(data=AuditEntriesResponse(
            entries=response_entries,
            total=len(entries),
            offset=offset,
            limit=limit
        ))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/verify/{entry_id}", response_model=SuccessResponse[VerificationReport])
async def verify_audit_entry(
    request: Request,
    entry_id: str = Path(..., description="Audit entry ID to verify"),
    auth: AuthContext = Depends(require_admin)
):
    """
    Verify audit entry integrity.
    
    Checks cryptographic signatures and hash chain integrity.
    Requires ADMIN role or higher.
    """
    audit_service = await _get_audit_service(request)
    
    try:
        # Get verification report
        report = await audit_service.get_verification_report()
        
        # Note: In a real implementation, would verify specific entry
        # For now, return general verification report
        return SuccessResponse(data=report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export", response_model=SuccessResponse[AuditExportResponse])
async def export_audit_data(
    request: Request,
    auth: AuthContext = Depends(require_admin),
    start_date: Optional[datetime] = Query(None, description="Export start date"),
    end_date: Optional[datetime] = Query(None, description="Export end date"),
    format: str = Query("jsonl", pattern="^(json|jsonl|csv)$", description="Export format")
):
    """
    Export audit data in specified format.
    
    Returns audit data for download or inline for small datasets.
    Requires ADMIN role or higher.
    """
    audit_service = await _get_audit_service(request)
    
    try:
        # Export data
        export_data = await audit_service.export_audit_data(
            start_date=start_date,
            end_date=end_date,
            format=format
        )
        
        # For small exports, return inline
        # For large exports, would typically upload to storage and return URL
        lines = export_data.split('\n')
        total_entries = len([l for l in lines if l.strip()])
        
        if total_entries > 1000:
            # In production, would upload to S3/storage and return URL
            return SuccessResponse(data=AuditExportResponse(
                format=format,
                total_entries=total_entries,
                export_url=f"/v1/audit/export/download/{format}",  # Placeholder
                export_data=None
            ))
        else:
            return SuccessResponse(data=AuditExportResponse(
                format=format,
                total_entries=total_entries,
                export_url=None,
                export_data=export_data
            ))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))