import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import Service
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.audit_schemas_v1 import AuditLogEntry  # Import from schemas

logger = logging.getLogger(__name__)


class AuditService(Service):
    """Service for persisting audit log entries with buffering and rotation."""

    def __init__(
        self,
        log_path: str = "audit_logs.jsonl",
        rotation_size_mb: int = 100,
        retention_days: int = 90,
    ):
        super().__init__()
        self.log_path = Path(log_path)
        self.rotation_size_mb = rotation_size_mb
        self.retention_days = retention_days
        self._buffer: List[AuditLogEntry] = []
        self._flush_task: Optional[asyncio.Task] = None

    async def start(self):
        await super().start()
        await asyncio.to_thread(self.log_path.touch, exist_ok=True)

    async def stop(self):
        await super().stop()

    async def log_action(
        self,
        handler_action: HandlerActionType,
        context: Dict[str, Any],
        outcome: Optional[str] = None,
    ) -> None:
        """Log an action with context and outcome."""
        entry = AuditLogEntry(
            event_id=str(uuid.uuid4()),
            event_timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=handler_action.value,
            originator_id=context.get("thought_id", "unknown"),
            target_id=context.get("target_id"),
            event_summary=self._generate_summary(handler_action, context, outcome),  # Pass outcome
            event_payload=context,
            agent_profile=context.get("agent_profile"),
            round_number=context.get("round_number"),
            thought_id=context.get("thought_id"),
            task_id=context.get("task_id") or context.get("source_task_id"),  # Handle both keys
        )
        self._buffer.append(entry)
        if len(self._buffer) >= 100:  # Flush every 100 entries
            await self._flush_buffer()

    async def _flush_buffer(self) -> None:
        """Flush buffered entries to disk."""
        if not self._buffer:
            return
        if await self._should_rotate():
            await self._rotate_log()
        entries_to_write = self._buffer.copy()
        self._buffer.clear()
        await asyncio.to_thread(self._write_entries, entries_to_write)

    async def query_audit_log(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        event_types: Optional[List[str]] = None,
        thought_id: Optional[str] = None,
    ) -> List[AuditLogEntry]:
        """Query audit logs with filters."""
        # Placeholder: implement log search logic as needed
        return []

    def _write_entries(self, entries: List[AuditLogEntry]) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            for entry in entries:
                f.write(entry.model_dump_json() + "\n")

    async def _should_rotate(self) -> bool:
        if not self.log_path.exists():
            return False
        size_mb = self.log_path.stat().st_size / (1024 * 1024)
        return size_mb >= self.rotation_size_mb

    async def _rotate_log(self) -> None:
        # Simple rotation: rename current log and start new
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        rotated = self.log_path.with_name(f"{self.log_path.stem}_{ts}.jsonl")
        self.log_path.rename(rotated)

    def _generate_summary(
        self, handler_action: HandlerActionType, context: Dict[str, Any], outcome: Optional[str] = None
    ) -> str:
        """Generate a summary including outcome if provided."""
        base_summary = f"{handler_action.value} action for thought {context.get('thought_id', 'unknown')}"
        if outcome:
            return f"{base_summary} - {outcome}"
        return base_summary
