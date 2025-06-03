from __future__ import annotations

import asyncio
from typing import List, Optional

from ..models import Message
from ..transport import Transport

class MessagesResource:
    def __init__(self, transport: Transport):
        self._transport = transport

    async def send(self, content: str, channel_id: str = "api") -> Message:
        payload = {"content": content, "channel_id": channel_id}
        resp = await self._transport.request("POST", "/v1/messages", json=payload)
        data = resp.json()
        return Message(
            id=data.get("id", ""),
            content=content,
            author_id=data.get("author_id", ""),
            author_name=data.get("author_name", ""),
            channel_id=channel_id,
            timestamp=data.get("timestamp"),
        )

    async def list(self, limit: int = 10) -> List[Message]:
        resp = await self._transport.request("GET", "/v1/messages", params={"limit": limit})
        messages = []
        for item in resp.json().get("messages", []):
            messages.append(Message(**item))
        return messages

    async def get_response(self, timeout: float = 30.0) -> Optional[Message]:
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            resp = await self._transport.request("GET", "/v1/status")
            data = resp.json().get("last_response")
            if data:
                return Message(**data)
            if asyncio.get_event_loop().time() >= deadline:
                return None
            await asyncio.sleep(1)
