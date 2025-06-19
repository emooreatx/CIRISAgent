from __future__ import annotations

import asyncio
from typing import List, Optional

from ..models import Message
from ..transport import Transport

class MessagesResource:
    def __init__(self, transport: Transport):
        self._transport = transport

    async def send(self, content: str, channel_id: str = "api_default", 
                   author_id: str = "sdk_user", author_name: str = "SDK User",
                   message_id: Optional[str] = None) -> Message:
        import uuid
        from datetime import datetime, timezone
        
        if message_id is None:
            message_id = str(uuid.uuid4())
            
        payload = {
            "message_id": message_id,
            "content": content,
            "channel_id": channel_id,
            "author_id": author_id,
            "author_name": author_name,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        resp = await self._transport.request("POST", "/api/v1/message", json=payload)
        data = resp.json()
        return Message(
            id=message_id,
            content=content,
            author_id=author_id,
            author_name=author_name,
            channel_id=channel_id,
            timestamp=payload["timestamp"],
        )

    async def list(self, channel_id: str = "api_default", limit: int = 10) -> List[Message]:
        resp = await self._transport.request("GET", f"/api/v1/messages/{channel_id}", params={"limit": limit})
        messages = []
        for item in resp.json().get("messages", []):
            messages.append(Message(
                id=item.get("message_id", ""),
                content=item.get("content", ""),
                author_id=item.get("author_id", ""),
                author_name=item.get("author_name", ""),
                channel_id=channel_id,
                timestamp=item.get("timestamp"),
            ))
        return messages

    async def wait_for_response(self, channel_id: str = "api_default", 
                                after_message_id: str = None, 
                                timeout: float = 30.0) -> Optional[Message]:
        """Wait for a response from the agent in the specified channel."""
        import asyncio
        
        start_time = asyncio.get_event_loop().time()
        last_seen_id = after_message_id
        
        while True:
            if asyncio.get_event_loop().time() - start_time > timeout:
                return None
                
            messages = await self.list(channel_id=channel_id, limit=20)
            
            # Look for new messages from the agent (not from SDK user)
            for msg in messages:
                # Skip messages we've already seen
                if last_seen_id and msg.id == last_seen_id:
                    break
                    
                # Check if this is from the agent (not the SDK user)
                if msg.author_id != "sdk_user" and msg.author_name != "SDK User":
                    return msg
                    
            await asyncio.sleep(1)
