from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime

from ..transport import Transport
from ..models import AuditEntryResponse, AuditEntryDetailResponse, AuditEntriesResponse, AuditExportResponse

class AuditResource:
    """Access audit log entries from the CIRIS Engine API.

    The audit system provides an immutable trail of all system actions,
    supporting compliance, debugging, and observability needs.
    """

    def __init__(self, transport: Transport):
        self._transport = transport

    async def query_entries(
        self,
        *,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        actor: Optional[str] = None,
        event_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        search: Optional[str] = None,
        severity: Optional[str] = None,
        outcome: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> AuditEntriesResponse:
        """Query audit entries with flexible filtering.

        Args:
            start_time: Start of time range to query
            end_time: End of time range to query
            actor: Filter by actor (who performed the action)
            event_type: Filter by event type
            entity_id: Filter by entity ID affected
            search: Search text in audit details
            severity: Filter by severity (info, warning, error)
            outcome: Filter by outcome (success, failure)
            limit: Maximum results to return (1-1000)
            offset: Results offset for pagination

        Returns:
            AuditEntriesResponse with entries and pagination info
        """
        params = {
            "limit": limit,
            "offset": offset
        }

        # Add optional filters
        if start_time:
            params["start_time"] = start_time.isoformat()
        if end_time:
            params["end_time"] = end_time.isoformat()
        if actor:
            params["actor"] = actor
        if event_type:
            params["event_type"] = event_type
        if entity_id:
            params["entity_id"] = entity_id
        if search:
            params["search"] = search
        if severity:
            params["severity"] = severity
        if outcome:
            params["outcome"] = outcome

        resp = await self._transport.request("GET", "/v1/audit", params=params)
        data = resp.json()
        return AuditEntriesResponse(**data["data"])

    async def get_entry(
        self,
        entry_id: str,
        *,
        verify: bool = False
    ) -> AuditEntryDetailResponse:
        """Get specific audit entry by ID with optional verification.

        Args:
            entry_id: The audit entry ID to retrieve
            verify: Include verification information (signature, hash chain status)

        Returns:
            AuditEntryDetailResponse with entry and optional verification data
        """
        params = {"verify": str(verify).lower()}
        resp = await self._transport.request("GET", f"/v1/audit/{entry_id}", params=params)
        data = resp.json()
        return AuditEntryDetailResponse(**data["data"])

    async def export_audit(
        self,
        *,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        format: str = "jsonl",
        include_verification: bool = False
    ) -> AuditExportResponse:
        """Export audit data for compliance and analysis.

        Args:
            start_date: Export start date
            end_date: Export end date
            format: Export format (json, jsonl, csv)
            include_verification: Include verification data in export

        Returns:
            AuditExportResponse with export data or download URL

        Note:
            For small exports (<1000 entries), data is returned inline.
            For larger exports, a download URL is provided.
        """
        params = {
            "format": format,
            "include_verification": str(include_verification).lower()
        }

        if start_date:
            params["start_date"] = start_date.isoformat()
        if end_date:
            params["end_date"] = end_date.isoformat()

        resp = await self._transport.request("GET", "/v1/audit/export", params=params)
        data = resp.json()
        return AuditExportResponse(**data["data"])
