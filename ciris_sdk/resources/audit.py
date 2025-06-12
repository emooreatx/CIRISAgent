from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..transport import Transport

class AuditResource:
    """Access audit log entries from the CIRIS Engine API."""

    def __init__(self, transport: Transport):
        self._transport = transport

    async def list(self, event_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        params = {"limit": limit}
        if event_type:
            params["event_type"] = event_type
        resp = await self._transport.request("GET", "/v1/audit", params=params)
        return resp.json()

    async def query(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query audit logs with advanced filters."""
        resp = await self._transport.request("POST", "/v1/audit/query", json=query)
        return resp.json()

    async def log(self, event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Log a custom audit entry."""
        payload = {
            "event_type": event_type,
            "event_data": event_data
        }
        resp = await self._transport.request("POST", "/v1/audit/log", json=payload)
        return resp.json()
