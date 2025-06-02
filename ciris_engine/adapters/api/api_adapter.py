import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

from ciris_engine.protocols.services import CommunicationService, WiseAuthorityService
class APIAdapter(CommunicationService, WiseAuthorityService):
    """Adapter for HTTP API communication and WA interactions.

    Incoming messages are delegated to ``APIObserver`` for processing. This
    adapter simply stores outgoing responses for retrieval by the API layer.
    """

    def __init__(self):
        self.responses: Dict[str, Any] = {}

    async def start(self):
        pass

    async def stop(self):
        pass

    async def send_message(self, channel_id: str, content: str) -> bool:
        response_id = str(uuid.uuid4())
        self.responses[response_id] = {
            "channel_id": channel_id,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return True

    async def fetch_messages(self, channel_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        return []

    async def fetch_guidance(self, context: Dict[str, Any]) -> Optional[str]:
        return None

    async def send_deferral(self, thought_id: str, reason: str) -> bool:
        self.responses[f"deferral_{thought_id}"] = {
            "type": "deferral",
            "thought_id": thought_id,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return True
