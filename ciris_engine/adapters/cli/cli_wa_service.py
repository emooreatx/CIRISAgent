import asyncio
import logging
from typing import Dict, Any, Optional

from ciris_engine.protocols.services import WiseAuthorityService

logger = logging.getLogger(__name__)

class CLIWiseAuthorityService(WiseAuthorityService):
    """CLI-based WA service that prompts user for guidance"""

    def __init__(self):
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
        return True
