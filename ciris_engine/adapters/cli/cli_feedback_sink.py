import logging
from typing import Any, Dict, Optional
from ciris_engine.ports import FeedbackSink
from ciris_engine.adapters.cli.cli_adapter import CLIAdapter
from ciris_engine import persistence
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, ThoughtStatus
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class CLIFeedbackSink(FeedbackSink):
    """Process incoming feedback/corrections from CLI (stdin or event queue)."""
    def __init__(self, adapter: CLIAdapter, deferral_channel_id: Optional[str]):
        self.adapter = adapter
        self.client = adapter.client
        self.deferral_channel_id = deferral_channel_id
    async def start(self):
        pass
    async def stop(self):
        pass
    async def process_feedback(self, msg: Any, raw_message: Any) -> bool:
        # For CLI, just print and create a correction thought for demonstration
        print(f"[CLI FEEDBACK] Received feedback: {msg} | Raw: {raw_message}")
        # Simulate follow-up thought creation
        now_iso = datetime.now(timezone.utc).isoformat()
        thought_id = f"th_corr_{getattr(msg, 'task_id', 'unknown')}_{now_iso[-4:]}"
        persistence.add_thought(
            Thought(
                thought_id=thought_id,
                source_task_id=getattr(msg, 'task_id', 'unknown'),
                parent_thought_id=getattr(msg, 'thought_id', None),
                thought_type="correction",
                status=ThoughtStatus.PENDING,
                created_at=now_iso,
                updated_at=now_iso,
                round_number=0,
                content=f"CLI Feedback: {getattr(msg, 'content', str(msg))}",
                priority=1,
                processing_context={
                    "is_wa_feedback": True,
                    "wa_author_id": getattr(msg, 'author_id', 'cli'),
                    "wa_author_name": getattr(msg, 'author_name', 'cli'),
                    "wa_message_id": getattr(msg, 'message_id', 'cli'),
                    "wa_timestamp": now_iso,
                    "context": getattr(msg, 'context', {}),
                },
            )
        )
        logger.info("CLIFeedbackSink: created correction thought %s", thought_id)
        return True
