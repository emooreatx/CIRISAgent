import asyncio
import logging
import uuid
from typing import List, Optional
from datetime import datetime, timezone

from ciris_engine.protocols.services import WiseAuthorityService
from ciris_engine.schemas.telemetry.core import (
    ServiceCorrelation,
    ServiceCorrelationStatus,
)
from ciris_engine.schemas.services.context import GuidanceContext, DeferralContext
from ciris_engine.logic import persistence
from ciris_engine.logic.services.infrastructure.time import TimeService

logger = logging.getLogger(__name__)

class CLIWiseAuthorityService(WiseAuthorityService):
    """CLI-based WA service that prompts user for guidance"""

    def __init__(self, time_service: Optional[TimeService] = None) -> None:
        super().__init__()
        self.time_service = time_service or TimeService()
        self.deferral_log: List[dict] = []

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
            "timestamp": self.time_service.now().timestamp(),
            "context": context.model_dump()
        }

        self.deferral_log.append(deferral_entry)

        # Enhanced CLI deferral output
        print(f"\n{'='*60}")
        print("[CIRIS DEFERRAL REPORT]")
        print(f"Thought ID: {context.thought_id}")
        print(f"Task ID: {context.task_id}")
        print(f"Reason: {context.reason}")
        print(f"Timestamp: {self.time_service.now().isoformat()}Z")

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

        now = datetime.now(timezone.utc)
        corr = ServiceCorrelation(
            correlation_id=str(uuid.uuid4()),
            service_type="cli",
            handler_name="CLIWiseAuthorityService",
            action_type="send_deferral",
            created_at=now,
            updated_at=now,
            timestamp=now,
            status=ServiceCorrelationStatus.COMPLETED
        )
        persistence.add_correlation(corr)
        return True
