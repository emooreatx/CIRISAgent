from __future__ import annotations

from typing import Any, List, Optional, Dict

from ..transport import Transport

class MemoryResource:
    def __init__(self, transport: Transport):
        self._transport = transport

    async def store(self, scope: str, key: str, value: Any) -> None:
        payload = {"key": key, "value": value}
        await self._transport.request("POST", f"/v1/memory/{scope}/store", json=payload)

    async def list_scopes(self) -> List[str]:
        resp = await self._transport.request("GET", "/v1/memory/scopes")
        return resp.json().get("scopes", [])

    async def fetch(self, scope: str, key: str) -> Optional[Any]:
        params = {"scope": scope, "key": key}
        resp = await self._transport.request("GET", "/v1/memory/fetch", params=params)
        return resp.json().get("value")

    async def query(self, scope: str, prefix: str = "", limit: int = 10) -> Any:
        params = {"scope": scope, "prefix": prefix, "limit": limit}
        resp = await self._transport.request("GET", "/v1/memory/query", params=params)
        return resp.json()

    async def get_entries(self, scope: str) -> List[Dict[str, Any]]:
        """Get all entries in a specific memory scope."""
        resp = await self._transport.request("GET", f"/v1/memory/{scope}/entries")
        return resp.json().get("entries", [])

    async def search(
        self,
        query: str,
        scope: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Search memory entries."""
        payload = {"query": query, "limit": limit}
        if scope:
            payload["scope"] = scope
        resp = await self._transport.request("POST", "/v1/memory/search", json=payload)
        return resp.json()

    async def recall(
        self,
        node_id: str,
        scope: Optional[str] = None,
        node_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Recall specific memory."""
        payload = {"node_id": node_id}
        if scope:
            payload["scope"] = scope
        if node_type:
            payload["node_type"] = node_type
        resp = await self._transport.request("POST", "/v1/memory/recall", json=payload)
        return resp.json()

    async def forget(self, scope: str, node_id: str) -> Dict[str, Any]:
        """Delete/forget a specific memory entry."""
        resp = await self._transport.request("DELETE", f"/v1/memory/{scope}/{node_id}")
        return resp.json()

    async def get_timeseries(
        self,
        scope: Optional[str] = None,
        hours: int = 24,
        correlation_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get memory timeseries data."""
        params = {"hours": str(hours)}
        if scope:
            params["scope"] = scope
        if correlation_types:
            params["correlation_types"] = ",".join(correlation_types)
        resp = await self._transport.request("GET", "/v1/memory/timeseries", params=params)
        return resp.json()
