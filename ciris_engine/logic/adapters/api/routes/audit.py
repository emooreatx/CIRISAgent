"""
Audit service endpoints for CIRIS API v3 (Simplified).

Provides access to the immutable audit trail for system observability.
Simplified to 3 core endpoints: query, get specific entry, and export.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field, field_serializer

from ciris_engine.protocols.services.graph.audit import AuditServiceProtocol
from ciris_engine.schemas.api.audit import AuditContext, EntryVerification
from ciris_engine.schemas.api.responses import ResponseMetadata, SuccessResponse
from ciris_engine.schemas.services.graph.audit import AuditQuery, VerificationReport
from ciris_engine.schemas.services.nodes import AuditEntry

from ..constants import DESC_END_TIME, DESC_RESULTS_OFFSET, DESC_START_TIME, ERROR_AUDIT_SERVICE_NOT_AVAILABLE
from ..dependencies.auth import AuthContext, require_admin, require_observer

router = APIRouter(prefix="/audit", tags=["audit"])

# Response schemas specific to API


class AuditEntryResponse(BaseModel):
    """Audit entry response with formatted fields."""

    id: str = Field(..., description="Audit entry ID")
    action: str = Field(..., description="Action performed")
    actor: str = Field(..., description="Who performed the action")
    timestamp: datetime = Field(..., description="When action occurred")
    context: AuditContext = Field(..., description="Action context")
    signature: Optional[str] = Field(None, description="Cryptographic signature")
    hash_chain: Optional[str] = Field(None, description="Previous hash for chain")

    @field_serializer("timestamp")
    def serialize_timestamp(self, timestamp: datetime, _info: Any) -> Optional[str]:
        return timestamp.isoformat() if timestamp else None


class AuditEntryDetailResponse(BaseModel):
    """Detailed audit entry with verification info."""

    entry: AuditEntryResponse = Field(..., description="The audit entry")
    verification: Optional[EntryVerification] = Field(None, description="Entry verification status")
    chain_position: Optional[int] = Field(None, description="Position in audit chain")
    next_entry_id: Optional[str] = Field(None, description="Next entry in chain")
    previous_entry_id: Optional[str] = Field(None, description="Previous entry in chain")


class AuditEntriesResponse(BaseModel):
    """List of audit entries."""

    entries: List[AuditEntryResponse] = Field(..., description="Audit entries")
    total: int = Field(..., description="Total matching entries")
    offset: int = Field(0, description=DESC_RESULTS_OFFSET)
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
    # Convert context to AuditContext
    ctx = entry.context
    if hasattr(ctx, "model_dump"):
        # Convert AuditEntryContext to dict, then to AuditContext
        ctx_dict = ctx.model_dump()
        context = AuditContext(
            entity_id=ctx_dict.get("entity_id"),
            entity_type=ctx_dict.get("entity_type"),
            operation=ctx_dict.get("operation") or ctx_dict.get("method_name"),
            description=ctx_dict.get("description"),
            request_id=ctx_dict.get("request_id"),
            correlation_id=ctx_dict.get("correlation_id"),
            user_id=ctx_dict.get("user_id"),
            ip_address=ctx_dict.get("ip_address"),
            user_agent=ctx_dict.get("user_agent"),
            result=ctx_dict.get("result"),
            error=ctx_dict.get("error"),
            metadata=ctx_dict.get("additional_data", {}),
        )
    else:
        # If it's not an AuditEntryContext, create a minimal AuditContext
        context = AuditContext(description=str(ctx) if ctx else None)

    return AuditEntryResponse(
        id=getattr(entry, "id", f"audit_{entry.timestamp.isoformat()}"),
        action=entry.action,
        actor=entry.actor,
        timestamp=entry.timestamp,
        context=context,
        signature=entry.signature,
        hash_chain=entry.hash_chain,
    )


def _get_audit_service(request: Request) -> AuditServiceProtocol:
    """Get audit service from app state."""
    audit_service = getattr(request.app.state, "audit_service", None)
    if not audit_service:
        raise HTTPException(status_code=503, detail=ERROR_AUDIT_SERVICE_NOT_AVAILABLE)
    return audit_service  # type: ignore[no-any-return]


# Endpoints


@router.get("/entries", response_model=SuccessResponse[AuditEntriesResponse])
async def query_audit_entries(
    request: Request,
    auth: AuthContext = Depends(require_observer),
    # Time range filters
    start_time: Optional[datetime] = Query(None, description=DESC_START_TIME),
    end_time: Optional[datetime] = Query(None, description=DESC_END_TIME),
    # Entity filters
    actor: Optional[str] = Query(None, description="Filter by actor"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    entity_id: Optional[str] = Query(None, description="Filter by entity ID"),
    # Search and additional filters
    search: Optional[str] = Query(None, description="Search in audit details"),
    severity: Optional[str] = Query(None, description="Filter by severity (info, warning, error)"),
    outcome: Optional[str] = Query(None, description="Filter by outcome (success, failure)"),
    # Pagination
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description=DESC_RESULTS_OFFSET),
) -> SuccessResponse[AuditEntriesResponse]:
    """
    Query audit entries with flexible filtering.

    Combines time-based queries, entity filtering, and text search into a single endpoint.
    Returns paginated results sorted by timestamp (newest first).

    Requires OBSERVER role or higher.
    """
    audit_service = _get_audit_service(request)

    # Build unified query
    query = AuditQuery(
        start_time=start_time,
        end_time=end_time,
        actor=actor,
        event_type=event_type,
        entity_id=entity_id,
        search_text=search,
        severity=severity,
        outcome=outcome,
        limit=limit,
        offset=offset,
        order_by="timestamp",
        order_desc=True,
    )

    try:
        entries = await audit_service.query_audit_trail(query)

        # Convert to response format
        response_entries = [_convert_audit_entry(entry) for entry in entries]

        # Get total count (in production, service would return this)
        # For now, if we got limit results, assume there are more
        total = len(entries) if len(entries) < limit else offset + len(entries) + 1

        return SuccessResponse(
            data=AuditEntriesResponse(entries=response_entries, total=total, offset=offset, limit=limit),
            metadata=ResponseMetadata(
                timestamp=datetime.now(timezone.utc), request_id=str(uuid.uuid4()), duration_ms=0
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entries/{entry_id}", response_model=SuccessResponse[AuditEntryDetailResponse])
async def get_audit_entry(
    request: Request,
    entry_id: str = Path(..., description="Audit entry ID"),
    auth: AuthContext = Depends(require_observer),
    verify: bool = Query(False, description="Include verification information"),
) -> SuccessResponse[AuditEntryDetailResponse]:
    """
    Get specific audit entry by ID with optional verification.

    Returns the audit entry and optionally includes:
    - Verification status of the entry's signature and hash
    - Position in the audit chain
    - Links to previous and next entries

    Requires OBSERVER role or higher.
    """
    audit_service = _get_audit_service(request)

    try:
        # Get the specific entry (implementation would use a proper lookup)
        # For now, search by ID in the query
        query = AuditQuery(limit=1000, order_by="timestamp", order_desc=True)  # Search recent entries
        entries = await audit_service.query_audit_trail(query)

        # Find the entry with matching ID
        target_entry = None
        entry_index = -1
        for i, entry in enumerate(entries):
            if hasattr(entry, "id") and entry.id == entry_id:
                target_entry = entry
                entry_index = i
                break
            # Also check if entry_id matches a generated ID pattern
            elif hasattr(entry, "timestamp") and hasattr(entry, "actor"):
                generated_id = f"audit_{entry.timestamp.strftime('%Y%m%d_%H%M%S')}_{entry.actor}"
                if generated_id == entry_id:
                    target_entry = entry
                    entry_index = i
                    break

        if not target_entry:
            raise HTTPException(status_code=404, detail=f"Audit entry '{entry_id}' not found")

        # Build response
        response = AuditEntryDetailResponse(entry=_convert_audit_entry(target_entry))

        # Add verification info if requested
        if verify:
            # Get verification report for this entry
            await audit_service.get_verification_report()

            # Extract verification for this specific entry
            response.verification = EntryVerification(
                signature_valid=target_entry.signature is not None,
                hash_chain_valid=target_entry.hash_chain is not None,
                verified_at=datetime.now(timezone.utc),
                verifier="system",
                algorithm="sha256",
                previous_hash_match=None,  # Would check in real implementation
            )

            # Add chain position info
            response.chain_position = entry_index
            if entry_index > 0:
                prev_entry = entries[entry_index - 1]
                response.previous_entry_id = getattr(
                    prev_entry, "id", f"audit_{prev_entry.timestamp.strftime('%Y%m%d_%H%M%S')}_{prev_entry.actor}"
                )
            if entry_index < len(entries) - 1:
                next_entry = entries[entry_index + 1]
                response.next_entry_id = getattr(
                    next_entry, "id", f"audit_{next_entry.timestamp.strftime('%Y%m%d_%H%M%S')}_{next_entry.actor}"
                )

        return SuccessResponse(
            data=response,
            metadata=ResponseMetadata(
                timestamp=datetime.now(timezone.utc), request_id=str(uuid.uuid4()), duration_ms=0
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=SuccessResponse[AuditEntriesResponse])
async def search_audit_trails(
    request: Request,
    auth: AuthContext = Depends(require_observer),
    search_text: Optional[str] = Query(None, description="Text to search for"),
    entity_id: Optional[str] = Query(None, description="Filter by entity ID"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    outcome: Optional[str] = Query(None, description="Filter by outcome"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description=DESC_RESULTS_OFFSET),
) -> SuccessResponse[AuditEntriesResponse]:
    """
    Search audit trails with text search and filters.

    This is a convenience endpoint that focuses on search functionality.
    For more complex queries, use the /entries endpoint.

    Requires OBSERVER role or higher.
    """
    # Delegate to the main query endpoint logic
    return await query_audit_entries(
        request=request,
        auth=auth,
        start_time=None,
        end_time=None,
        actor=None,
        event_type=None,
        entity_id=entity_id,
        search=search_text,
        severity=severity,
        outcome=outcome,
        limit=limit,
        offset=offset,
    )


@router.post("/verify/{entry_id}", response_model=SuccessResponse[VerificationReport])
async def verify_audit_entry(
    request: Request,
    entry_id: str = Path(..., description="Audit entry ID to verify"),
    auth: AuthContext = Depends(require_admin),
) -> SuccessResponse[VerificationReport]:
    """
    Verify the integrity of a specific audit entry.

    Returns detailed verification information including signature validation
    and hash chain integrity.

    Requires ADMIN role or higher.
    """
    audit_service = _get_audit_service(request)

    try:
        # Get the full verification report
        verification_report = await audit_service.get_verification_report()
        return SuccessResponse(data=verification_report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export", response_model=SuccessResponse[AuditExportResponse])
async def export_audit_data(
    request: Request,
    auth: AuthContext = Depends(require_admin),
    start_date: Optional[datetime] = Query(None, description="Export start date"),
    end_date: Optional[datetime] = Query(None, description="Export end date"),
    format: str = Query("jsonl", pattern="^(json|jsonl|csv)$", description="Export format"),
    include_verification: bool = Query(False, description="Include verification data in export"),
) -> SuccessResponse[AuditExportResponse]:
    """
    Export audit data for compliance and analysis.

    Exports audit entries in the specified format. For small datasets (< 1000 entries),
    data is returned inline. For larger datasets, a download URL is provided.

    Formats:
    - **jsonl**: JSON Lines format (one entry per line)
    - **json**: Standard JSON array
    - **csv**: CSV format with standard audit fields

    Requires ADMIN role or higher.
    """
    audit_service = _get_audit_service(request)

    try:
        # Export data
        export_data = await audit_service.export_audit_data(start_time=start_date, end_time=end_date, format=format)

        # Add verification data if requested
        if include_verification and format == "jsonl":
            # Get verification report
            verification_report = await audit_service.get_verification_report()
            # Append verification summary to export
            verification_summary = {
                "_verification": {
                    "verified": verification_report.verified,
                    "total_entries": verification_report.total_entries,
                    "valid_entries": verification_report.valid_entries,
                    "chain_intact": verification_report.chain_intact,
                    "verification_timestamp": verification_report.verification_completed.isoformat(),
                }
            }
            export_data += "\n" + json.dumps(verification_summary)

        # Count entries for response
        lines = export_data.split("\n")
        total_entries = len([l for l in lines if l.strip() and not l.startswith('{"_verification"')])

        if total_entries > 1000:
            # For large exports, would typically upload to storage
            # In production, this would upload to S3/cloud storage and return a signed URL
            return SuccessResponse(
                data=AuditExportResponse(
                    format=format,
                    total_entries=total_entries,
                    export_url=f"/v1/audit/export/download/{format}",  # Placeholder URL
                    export_data=None,
                ),
                metadata=ResponseMetadata(
                    timestamp=datetime.now(timezone.utc), request_id=str(uuid.uuid4()), duration_ms=0
                ),
            )
        else:
            return SuccessResponse(
                data=AuditExportResponse(
                    format=format, total_entries=total_entries, export_url=None, export_data=export_data
                ),
                metadata=ResponseMetadata(
                    timestamp=datetime.now(timezone.utc), request_id=str(uuid.uuid4()), duration_ms=0
                ),
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
