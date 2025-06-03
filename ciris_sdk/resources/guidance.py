from __future__ import annotations

from typing import Any

from ..transport import Transport

class GuidanceResource:
    def __init__(self, transport: Transport):
        self._transport = transport

    async def fetch(self, context: dict[str, Any]) -> Any:
        resp = await self._transport.request("POST", "/v1/guidance", json=context)
        return resp.json()
