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
from ciris_engine.schemas.wa_context_schemas_v1 import GuidanceContext, DeferralContext
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

    async def fetch_guidance(self, context: GuidanceContext) -> Optional[str]:
        """Prompt user for guidance on deferred decision"""
        print("\n[WA GUIDANCE REQUEST]")
        print(f"Question: {context.question}")
        print(f"Task ID: {context.task_id}")
        if context.ethical_considerations:
            print(f"Ethical considerations: {', '.join(context.ethical_considerations)}")
        print("Please provide guidance (or 'skip' to defer):")
        try:
            guidance = await asyncio.to_thread(input, ">>> ")
            if guidance.lower() == 'skip':
                return None
            return guidance
        except Exception as e:
            logger.error(f"Failed to get CLI guidance: {e}")
            return None

    async def send_deferral(self, context: DeferralContext) -> bool:
        """Log deferral to CLI output with rich context"""
        deferral_entry = {
            "thought_id": context.thought_id,
            "reason": context.reason,
            "timestamp": asyncio.get_event_loop().time(),
            "context": context.model_dump()
        }
        
        self.deferral_log.append(deferral_entry)
        
        # Enhanced CLI deferral output
        print(f"\n{'='*60}")
        print("[CIRIS DEFERRAL REPORT]")
        print(f"Thought ID: {context.thought_id}")
        print(f"Task ID: {context.task_id}")
        print(f"Reason: {context.reason}")
        print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}Z")
        
        if context.defer_until:
            print(f"Defer until: {context.defer_until}")
        if context.priority:
            print(f"Priority: {context.priority}")
        if context.metadata:
            if "task_description" in context.metadata:
                print(f"Task: {context.metadata['task_description']}")
            if "attempted_action" in context.metadata:
                print(f"Attempted Action: {context.metadata['attempted_action']}")
            if "max_rounds_reached" in context.metadata and context.metadata["max_rounds_reached"] == "True":
                print("Note: Maximum processing rounds reached")
        
        print(f"{'='*60}")
        
        corr = ServiceCorrelation(
            correlation_id=str(uuid.uuid4()),
            service_type="cli",
            handler_name="CLIWiseAuthorityService",
            action_type="send_deferral",
            request_data=context.model_dump(),
            response_data={"status": "logged"},
            status=ServiceCorrelationStatus.COMPLETED,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        persistence.add_correlation(corr)
        return True
