import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ciris_engine.core.ports import DeferralSink
from ciris_engine.core import persistence
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, ThoughtStatus
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage # ERIC
from ciris_engine.services.base import Service
from ciris_engine.runtime.base_runtime import DiscordAdapter

try:
    from ciris_engine.services.discord_service import _truncate_discord_message
except Exception:
    def _truncate_discord_message(message: str, limit: int = 1900) -> str:
        return message if len(message) <= limit else message[:limit-3] + "..."

logger = logging.getLogger(__name__)


class DiscordDeferralSink(Service, DeferralSink):
    """Send deferral reports via Discord and handle WA correction replies."""

    def __init__(self, adapter: DiscordAdapter, deferral_channel_id: Optional[str]):
        super().__init__()
        self.adapter = adapter
        self.client = adapter.client
        self.deferral_channel_id = int(deferral_channel_id) if deferral_channel_id else None

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def send_deferral(
        self,
        task_id: str,
        thought_id: str,
        reason: str,
        package: Dict[str, Any],
    ) -> None:
        if not self.deferral_channel_id:
            logger.warning("DiscordDeferralSink: deferral channel not configured")
            return
        channel = self.client.get_channel(self.deferral_channel_id)
        if channel is None:
            channel = await self.client.fetch_channel(self.deferral_channel_id)
        if channel is None:
            logger.error("DiscordDeferralSink: cannot access deferral channel %s", self.deferral_channel_id)
            return
        if "metadata" in package and "user_nick" in package:
            report = (
                f"**Memory Deferral Report**\n"
                f"**Task ID:** `{task_id}`\n"
                f"**Deferred Thought ID:** `{thought_id}`\n"
                f"**User:** {package.get('user_nick')} Channel: {package.get('channel')}\n"
                f"**Reason:** {reason}\n"
                f"**Metadata:** ```json\n{json.dumps(package.get('metadata'), indent=2)}\n```"
            )
        else:
            report = (
                f"**Deferral Report**\n"
                f"**Task ID:** `{task_id}`\n"
                f"**Deferred Thought ID:** `{thought_id}`\n"
                f"**Reason:** {reason}\n"
                f"**Deferral Package:** ```json\n{json.dumps(package, indent=2)}\n```"
            )
        sent = await channel.send(_truncate_discord_message(report))
        persistence.save_deferral_report_mapping(
            str(sent.id), task_id, thought_id, package
        )

    async def process_possible_correction(self, msg: IncomingMessage, raw_message: Any) -> bool:
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

    def _create_correction_thought(
        self,
        original_task_id: str,
        corrected_thought_id: Optional[str],
        message: Any,
        deferral_data: Optional[Dict[str, Any]],
    ) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        thought_id = f"th_corr_{original_task_id}_{now_iso[-4:]}"
        orig_task = persistence.get_task_by_id(original_task_id)
        priority = orig_task.priority if orig_task else 1
        persistence.add_thought(
            Thought(
                thought_id=thought_id,
                source_task_id=original_task_id,
                related_thought_id=corrected_thought_id,
                thought_type="correction",
                status=ThoughtStatus.PENDING,
                created_at=now_iso,
                updated_at=now_iso,
                round_created=0,
                content=f"This message was received in response a deferral or prior task, which should be in your context. WA Correction by {message.author.name}: {message.content}",
                priority=priority,
                processing_context={
                    "is_wa_feedback": True,
                    "wa_author_id": str(message.author.id),
                    "wa_author_name": message.author.name,
                    "wa_message_id": str(message.id),
                    "wa_timestamp": message.created_at.isoformat(),
                    "deferral_package_content": deferral_data,
                },
            )
        )
        logger.info("DiscordDeferralSink: created correction thought %s", thought_id)
