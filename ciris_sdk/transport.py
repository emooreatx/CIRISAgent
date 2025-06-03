from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional
import httpx

from .exceptions import CIRISAPIError, CIRISConnectionError, CIRISTimeoutError

class Transport:
    def __init__(self, base_url: str, api_key: Optional[str], timeout: float):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "Transport":
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        if not self._client:
            raise RuntimeError("Transport not started")
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            resp = await self._client.request(method, url, headers=headers, **kwargs)
        except httpx.RequestError as exc:
            raise CIRISConnectionError(str(exc)) from exc
        if resp.status_code >= 400:
            raise CIRISAPIError(resp.status_code, resp.text)
        return resp
