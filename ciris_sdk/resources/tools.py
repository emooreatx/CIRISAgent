from __future__ import annotations

from typing import Any, List, Dict

from ..transport import Transport

class ToolsResource:
    def __init__(self, transport: Transport):
        self._transport = transport

    async def execute(self, name: str, args: dict[str, Any]) -> Any:
        payload = {"name": name, "args": args}
        resp = await self._transport.request("POST", "/v1/tools/execute", json=payload)
        return resp.json()

    async def list(self) -> List[str]:
        resp = await self._transport.request("GET", "/v1/tools")
        return resp.json().get("tools", [])

    async def validate(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate tool parameters before execution."""
        resp = await self._transport.request("POST", f"/v1/tools/{tool_name}/validate", json=parameters)
        return resp.json()
