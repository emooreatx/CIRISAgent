from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Deque, Dict, Tuple, Any

from ciris_engine.adapters.base import Service
from ciris_engine.schemas.telemetry_schemas_v1 import CompactTelemetry
from ciris_engine.schemas.context_schemas_v1 import SystemSnapshot
from .security import SecurityFilter

logger = logging.getLogger(__name__)


class TelemetryService(Service):
    """Collects and exposes basic telemetry for agent introspection."""

    def __init__(self, buffer_size: int = 1000, security_filter: SecurityFilter | None = None) -> None:
        super().__init__()
        self.buffer_size = buffer_size
        self._history: Dict[str, Deque[Tuple[datetime, float]]] = defaultdict(
            lambda: deque(maxlen=self.buffer_size)
        )
        self._filter = security_filter or SecurityFilter()
        self.start_time = datetime.utcnow()

    async def start(self) -> None:
        await super().start()
        logger.info("Telemetry service started")

    async def stop(self) -> None:
        await super().stop()
        logger.info("Telemetry service stopped")

    async def record_metric(self, metric_name: str, value: float = 1.0) -> None:
        sanitized = self._filter.sanitize(metric_name, value)
        if sanitized is None:
            logger.debug("Metric discarded by security filter: %s", metric_name)
            return
        name, val = sanitized
        self._history[name].append((datetime.utcnow(), float(val)))

    async def update_system_snapshot(self, snapshot: SystemSnapshot) -> None:
        """Update SystemSnapshot.telemetry with recent metrics."""
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=24)
        telemetry = CompactTelemetry()
        for name, records in self._history.items():
            records = [r for r in records if r[0] > cutoff]
            self._history[name] = deque(records, maxlen=self.buffer_size)
            count = len(records)
            if name == "message_processed":
                telemetry.messages_processed_24h = count
            elif name == "error":
                telemetry.errors_24h = count
            elif name == "thought":
                telemetry.thoughts_24h = count
        uptime = now - self.start_time
        telemetry.uptime_hours = round(uptime.total_seconds() / 3600, 2)
        telemetry.epoch_seconds = int(now.timestamp())
        snapshot.telemetry = telemetry

