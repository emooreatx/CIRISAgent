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
        """Submit a deferral to wise authority."""
        payload = {
            "thought_id": thought_id,
            "reason": reason
        }
        if context:
            payload["context"] = context
        resp = await self._transport.request("POST", "/v1/defer", json=payload)
        return resp.json()

    async def list_deferrals(self) -> List[Dict[str, Any]]:
        """Get list of all deferrals."""
        resp = await self._transport.request("GET", "/v1/wa/deferrals")
        return resp.json()

    async def get_deferral_detail(self, deferral_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific deferral."""
        resp = await self._transport.request("GET", f"/v1/wa/deferrals/{deferral_id}")
        return resp.json()

    async def submit_feedback(self, feedback: Dict[str, Any]) -> Dict[str, Any]:
        """Submit feedback to wise authority."""
        resp = await self._transport.request("POST", "/v1/wa/feedback", json=feedback)
        return resp.json()
