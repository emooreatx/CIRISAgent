import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from ciris_engine.protocols.services import WiseAuthorityService
from ciris_engine.schemas.correlation_schemas_v1 import (
    ServiceCorrelation,
    ServiceCorrelationStatus,
)
from ciris_engine import persistence

logger = logging.getLogger(__name__)

class CLIWiseAuthorityService(WiseAuthorityService):
    """CLI-based WA service that prompts user for guidance"""

    def __init__(self) -> None:
        self.deferral_log = []

    async def fetch_guidance(self, context: Dict[str, Any]) -> Optional[str]:
        """Prompt user for guidance on deferred decision"""
        print("\n[WA GUIDANCE REQUEST]")
        print(f"Context: {context}")
        print("Please provide guidance (or 'skip' to defer):")
        try:
            guidance = await asyncio.to_thread(input, ">>> ")
            if guidance.lower() == 'skip':
                return None
            return guidance
        except Exception as e:
            logger.error(f"Failed to get CLI guidance: {e}")
            return None

    async def send_deferral(self, thought_id: str, reason: str) -> bool:
        """Log deferral to CLI output"""
        self.deferral_log.append({
            "thought_id": thought_id,
            "reason": reason,
            "timestamp": asyncio.get_event_loop().time()
        })
        print(f"\n[DEFERRAL] Thought {thought_id}: {reason}")
        corr = ServiceCorrelation(
            correlation_id=str(uuid.uuid4()),
            service_type="cli",
            handler_name="CLIWiseAuthorityService",
            action_type="send_deferral",
            request_data={"thought_id": thought_id, "reason": reason},
            response_data={"status": "logged"},
            status=ServiceCorrelationStatus.COMPLETED,
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        persistence.add_correlation(corr)
        return True
