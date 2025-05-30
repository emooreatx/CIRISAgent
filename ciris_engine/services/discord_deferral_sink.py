import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ciris_engine.ports import DeferralSink
from ciris_engine import persistence
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, ThoughtStatus
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.services.base import Service
from ciris_engine.adapters.discord.discord_adapter import DiscordAdapter
from ciris_engine.adapters.discord.discord_deferral_sink import DiscordDeferralSink

logger = logging.getLogger(__name__)


class GenericDeferralSink(Service, DeferralSink):
    """Generic wrapper for deferral sinks (delegates to adapter-specific implementation)."""

    def __init__(self, adapter: DiscordAdapter, deferral_channel_id: Optional[str]):
        super().__init__()
        self.sink = DiscordDeferralSink(adapter, deferral_channel_id)

    async def send_deferral(
        self,
        task_id: str,
        thought_id: str,
        reason: str,
        package: Dict[str, Any],
    ) -> None:
        await self.sink.send_deferral(task_id, thought_id, reason, package)

    async def start(self):
        pass

    async def stop(self):
        pass
