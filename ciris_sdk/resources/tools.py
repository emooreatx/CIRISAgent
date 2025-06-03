from __future__ import annotations

from typing import Any

from ..transport import Transport

class ToolsResource:
    def __init__(self, transport: Transport):
        self._transport = transport

    async def execute(self, name: str, args: dict[str, Any]) -> Any:
        payload = {"name": name, "args": args}
        resp = await self._transport.request("POST", "/v1/tools/execute", json=payload)
        return resp.json()
