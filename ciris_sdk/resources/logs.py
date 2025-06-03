from __future__ import annotations

from ..transport import Transport

class LogsResource:
    """Access engine log files."""

    def __init__(self, transport: Transport):
        self._transport = transport

    async def fetch(self, filename: str, tail: int = 100) -> str:
        resp = await self._transport.request("GET", f"/v1/logs/{filename}", params={"tail": tail})
        return resp.text
