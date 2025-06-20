from __future__ import annotations

import asyncio
from typing import Optional

from .transport import Transport
from .resources.agent import AgentResource
from .resources.memory import MemoryResource
from .resources.visibility import VisibilityResource
from .resources.telemetry import TelemetryResource
from .resources.runtime import RuntimeResource
from .resources.auth import AuthResource
from .exceptions import CIRISTimeoutError, CIRISConnectionError

class CIRISClient:
    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self._transport = Transport(base_url, api_key, timeout)

        # Core resources matching new API structure
        self.agent = AgentResource(self._transport)
        self.memory = MemoryResource(self._transport)
        self.visibility = VisibilityResource(self._transport)
        self.telemetry = TelemetryResource(self._transport)
        self.runtime = RuntimeResource(self._transport)
        self.auth = AuthResource(self._transport)

    async def __aenter__(self) -> "CIRISClient":
        await self._transport.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._transport.__aexit__(exc_type, exc, tb)

    async def _request_with_retry(self, method: str, path: str, **kwargs) -> Any:
        for attempt in range(self.max_retries):
            try:
                return await self._transport.request(method, path, **kwargs)
            except CIRISConnectionError:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise
