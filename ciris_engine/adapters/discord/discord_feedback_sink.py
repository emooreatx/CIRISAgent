import logging
import re
import json
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from ciris_engine.ports import FeedbackSink
from ciris_engine import persistence
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, ThoughtStatus
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.adapters.discord.discord_adapter import DiscordAdapter

logger = logging.getLogger(__name__)

class DiscordFeedbackSink(FeedbackSink):
    """Process incoming feedback/corrections from Discord (WA, etc)."""
    def __init__(self, adapter: DiscordAdapter, deferral_channel_id: Optional[str]):
        self.adapter = adapter
        self.client = adapter.client
        self.deferral_channel_id = int(deferral_channel_id) if deferral_channel_id else None

    async def start(self):
        pass

    async def stop(self):
        pass

    async def process_feedback(self, msg: IncomingMessage, raw_message: Any) -> bool:
        if not self.deferral_channel_id or str(self.deferral_channel_id) != msg.channel_id:
            return False
        ref_id = getattr(raw_message, "reference", None)
        if not ref_id or not getattr(raw_message.reference, "message_id", None):
            return False
        ref_message_id = str(raw_message.reference.message_id)
        mapping = persistence.get_deferral_report_context(ref_message_id)
        if not mapping:
            return False
        task_id, corrected_thought_id, stored_package = mapping
        deferral_data = stored_package
        try:
            replied_content = raw_message.reference.resolved.content if raw_message.reference.resolved else None
        except Exception:
            replied_content = None
        if replied_content:
            m = re.search(r"```json\n(.*)\n```", replied_content, re.DOTALL)
            if m:
                try:
                    deferral_data = json.loads(m.group(1))
                except Exception:
                    pass
        self._create_correction_thought(task_id, corrected_thought_id, raw_message, deferral_data)
        return True

    def _create_correction_thought(self, original_task_id: str, corrected_thought_id: Optional[str], message: Any, deferral_data: Optional[Dict[str, Any]]) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        thought_id = f"th_corr_{original_task_id}_{now_iso[-4:]}"
        orig_task = persistence.get_task_by_id(original_task_id)
        priority = orig_task.priority if orig_task else 1
        persistence.add_thought(
            Thought(
                thought_id=thought_id,
                source_task_id=original_task_id,
                parent_thought_id=corrected_thought_id,
                thought_type="correction",
                status=ThoughtStatus.PENDING,
                created_at=now_iso,
                updated_at=now_iso,
                round_number=0,
                content=f"This message was received in response a deferral or prior task, which should be in your context. WA Correction by {message.author.name}: {message.content}",
                priority=priority,
                processing_context={
                    "is_wa_feedback": True,
                    "wa_author_id": str(message.author.id),
                    "wa_author_name": message.author.name,
                    "wa_message_id": str(message.id),
                    "wa_timestamp": message.created_at.isoformat(),
                    "context": deferral_data,
                },
            )
        )
        logger.info("DiscordFeedbackSink: created correction thought %s", thought_id)
