from __future__ import annotations

from typing import Any

from ..transport import Transport

class MemoryResource:
    def __init__(self, transport: Transport):
        self._transport = transport

    async def store(self, scope: str, key: str, value: Any) -> None:
        payload = {"key": key, "value": value}
        await self._transport.request("POST", f"/v1/memory/{scope}/store", json=payload)
