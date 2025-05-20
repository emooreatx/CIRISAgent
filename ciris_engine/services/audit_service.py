import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .base import Service
from ciris_engine.core.audit_schemas import AuditLogEntry
from ciris_engine.core.foundational_schemas import HandlerActionType

logger = logging.getLogger(__name__)


class AuditService(Service):
    """Minimal service for persisting audit log entries."""

    def __init__(self, log_path: str = "audit_logs.jsonl") -> None:
        super().__init__()
        self.log_path = Path(log_path)

    async def start(self):
        await super().start()
        await asyncio.to_thread(self.log_path.touch, exist_ok=True)

    async def stop(self):
        await super().stop()

    async def log_action(self, handler_action: HandlerActionType, context: Dict[str, Any]):
        """Persist an audit log entry derived from the given context."""
        event_type = context.pop("event_type", handler_action.name)
        entry = AuditLogEntry(
            event_id=str(uuid.uuid4()),
            event_timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            originator_id=context.get("originator_id", "unknown"),
            target_id=context.get("target_id"),
            event_summary=context.get("event_summary", ""),
            event_payload=context.get("event_payload"),
        )
        line = json.dumps(entry.model_dump(exclude_none=True))
        await asyncio.to_thread(self._append_line, line)

    def _append_line(self, line: str) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
