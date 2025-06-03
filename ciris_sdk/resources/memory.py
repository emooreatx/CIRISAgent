from __future__ import annotations

from typing import Any, List, Optional

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
