from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..transport import Transport

class GuidanceResource:
    def __init__(self, transport: Transport):
        self._transport = transport

    async def fetch(self, context: dict[str, Any]) -> Any:
        resp = await self._transport.request("POST", "/v1/guidance", json=context)
        return resp.json()

    async def submit_deferral(
        self,
        thought_id: str,
        reason: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Submit a deferral to wise authority.

        Note: This creates a deferral from the agent side.
        For viewing/resolving deferrals, use the client.wa resource.
        """
        payload = {
            "thought_id": thought_id,
            "reason": reason
        }
        if context:
            payload["context"] = context
        resp = await self._transport.request("POST", "/v1/defer", json=payload)
        return resp.json()
