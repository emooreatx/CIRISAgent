import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

from ciris_engine.schemas.correlation_schemas_v1 import (
    ServiceCorrelation,
    ServiceCorrelationStatus,
)
from ciris_engine import persistence

from ciris_engine.protocols.services import CommunicationService, WiseAuthorityService

class APIAdapter(CommunicationService, WiseAuthorityService):
    """Adapter for HTTP API communication and WA interactions."""

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
        persistence.add_correlation(
            ServiceCorrelation(
                correlation_id=response_id,
                service_type="api",
                handler_name="APIAdapter",
                action_type="send_message",
                request_data={"channel_id": channel_id, "content": content},
                response_data=self.responses[response_id],
                status=ServiceCorrelationStatus.COMPLETED,
                created_at=self.responses[response_id]["timestamp"],
                updated_at=self.responses[response_id]["timestamp"],
            )
        )
        return True

    async def fetch_messages(self, channel_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        return []

    async def fetch_guidance(self, context: Dict[str, Any]) -> Optional[str]:
        correlation_id = str(uuid.uuid4())
        persistence.add_correlation(
            ServiceCorrelation(
                correlation_id=correlation_id,
                service_type="api",
                handler_name="APIAdapter",
                action_type="fetch_guidance",
                request_data=context,
                status=ServiceCorrelationStatus.COMPLETED,
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
            )
        )
        return None

    async def send_deferral(self, thought_id: str, reason: str) -> bool:
        self.responses[f"deferral_{thought_id}"] = {
            "type": "deferral",
            "thought_id": thought_id,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        }
        persistence.add_correlation(
            ServiceCorrelation(
                correlation_id=f"deferral_{thought_id}",
                service_type="api",
                handler_name="APIAdapter",
                action_type="send_deferral",
                request_data={"thought_id": thought_id, "reason": reason},
                response_data=self.responses[f"deferral_{thought_id}"],
                status=ServiceCorrelationStatus.COMPLETED,
                created_at=self.responses[f"deferral_{thought_id}"]["timestamp"],
                updated_at=self.responses[f"deferral_{thought_id}"]["timestamp"],
            )
        )
        return True
