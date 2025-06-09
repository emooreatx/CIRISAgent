import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

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
        super().__init__()
        self.deferral_log: List[Dict[str, Any]] = []

    async def start(self) -> None:
        """Start the CLI wise authority service."""
        await super().start()

    async def stop(self) -> None:
        """Stop the CLI wise authority service."""
        await super().stop()

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

    async def send_deferral(self, thought_id: str, reason: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """Log deferral to CLI output with rich context"""
        deferral_entry = {
            "thought_id": thought_id,
            "reason": reason,
            "timestamp": asyncio.get_event_loop().time()
        }
        if context:
            deferral_entry["context"] = context
        
        self.deferral_log.append(deferral_entry)
        
        # Enhanced CLI deferral output
        print(f"\n{'='*60}")
        print("[CIRIS DEFERRAL REPORT]")
        print(f"Thought ID: {thought_id}")
        print(f"Reason: {reason}")
        print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}Z")
        
        if context:
            if "task_id" in context:
                print(f"Task ID: {context['task_id']}")
            if "task_description" in context:
                print(f"Task: {context['task_description']}")
            if "thought_content" in context and context["thought_content"]:
                print(f"Thought: {context['thought_content'][:200]}{'...' if len(context['thought_content']) > 200 else ''}")
            if "priority" in context:
                print(f"Priority: {context['priority']}")
            if "attempted_action" in context:
                print(f"Attempted Action: {context['attempted_action']}")
            if "max_rounds_reached" in context and context["max_rounds_reached"]:
                print("Note: Maximum processing rounds reached")
        
        print(f"{'='*60}")
        
        corr = ServiceCorrelation(
            correlation_id=str(uuid.uuid4()),
            service_type="cli",
            handler_name="CLIWiseAuthorityService",
            action_type="send_deferral",
            request_data={"thought_id": thought_id, "reason": reason, "context": context},
            response_data={"status": "logged"},
            status=ServiceCorrelationStatus.COMPLETED,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        persistence.add_correlation(corr)
        return True
