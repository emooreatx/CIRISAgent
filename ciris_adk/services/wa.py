"""WiseAuthorityService protocol for human or peer guidance."""

from __future__ import annotations

from typing import Any, Dict, Protocol


class WiseAuthorityService(Protocol):
    async def fetch_guidance(self, context: Dict[str, Any]) -> str | None:
        ...

    async def send_deferral(self, thought_id: str, reason: str) -> bool:
        ...

