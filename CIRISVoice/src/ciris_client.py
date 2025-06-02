import aiohttp
from typing import Optional, Dict, Any
import logging
import asyncio

logger = logging.getLogger(__name__)

class CIRISClient:
    def __init__(self, config):
        self.api_url = config.api_url
        self.api_key = config.api_key
        self.timeout = config.timeout
        self.channel_id = config.channel_id
        self.profile = config.profile

    async def send_message(self, content: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            payload = {
                "content": content,
                "channel_id": self.channel_id,
                "author_id": "voice_user",
                "author_name": "Voice User",
                "context": context or {"source": "wyoming_voice", "profile": self.profile}
            }
            try:
                async with session.post(
                    f"{self.api_url}/v1/messages",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error = await response.text()
                        logger.error(f"CIRIS API error: {error}")
                        return {"content": "I'm having trouble processing that request."}
            except asyncio.TimeoutError:
                logger.error("CIRIS API timeout")
                return {"content": "I need more time to think about that. Please try again."}
            except Exception as e:
                logger.error(f"CIRIS API exception: {e}")
                return {"content": "I'm experiencing technical difficulties."}

    async def get_response(self, message_id: str) -> Optional[str]:
        async with aiohttp.ClientSession() as session:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            async with session.get(
                f"{self.api_url}/v1/status",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("last_response", {}).get("content")
        return None
