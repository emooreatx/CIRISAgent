from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Callable, Deque, Dict, List, Optional, Tuple

import psutil

from ciris_engine.protocols.services import ServiceProtocol
from ciris_engine.protocols.services.infrastructure.resource_monitor import ResourceMonitorServiceProtocol
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from ciris_engine.logic.persistence import get_db_connection
from ciris_engine.schemas.services.resources_core import (
    ResourceBudget,
    ResourceLimit,
    ResourceSnapshot,
    ResourceAction,
)
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus

logger = logging.getLogger(__name__)

class ResourceSignalBus:
    """Simple signal bus for resource events."""

    def __init__(self) -> None:
        self._handlers: Dict[str, List[Callable[[str, str], asyncio.Future]]] = {
            "throttle": [],
            "defer": [],
            "reject": [],
            "shutdown": [],
        }

    def register(self, signal: str, handler: Callable[[str, str], asyncio.Future]) -> None:
        self._handlers.setdefault(signal, []).append(handler)

    async def emit(self, signal: str, resource: str) -> None:
        for handler in self._handlers.get(signal, []):
            try:
                await handler(signal, resource)
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("Signal handler error: %s", exc)

class ResourceMonitorService(ResourceMonitorServiceProtocol, ServiceProtocol):
    """Monitor system resources and enforce limits."""

    def __init__(self, budget: ResourceBudget, db_path: str, time_service: TimeServiceProtocol, signal_bus: Optional[ResourceSignalBus] = None) -> None:
        self.budget = budget
        self.db_path = db_path
        self.time_service = time_service
        self.snapshot = ResourceSnapshot()
        self.signal_bus = signal_bus or ResourceSignalBus()

        self._token_history: Deque[Tuple[datetime, int]] = deque(maxlen=86400)
        self._cpu_history: Deque[float] = deque(maxlen=60)
        self._last_action_time: Dict[str, datetime] = {}
        self._monitoring = False
        self._process = psutil.Process()
        self._start_time: Optional[datetime] = None

    async def start(self) -> None:
        self._monitoring = True
        self._start_time = self.time_service.now()
        asyncio.create_task(self._monitor_loop())
        logger.info("Resource monitor started")

    async def stop(self) -> None:
        self._monitoring = False
        logger.info("Resource monitor stopped")

    async def _monitor_loop(self) -> None:
        while self._monitoring:
            try:
                await self._update_snapshot()
                await self._check_limits()
                await asyncio.sleep(1)
            except Exception as exc:  # pragma: no cover - unexpected
                logger.error("Resource monitor error: %s", exc)
                await asyncio.sleep(5)

    async def _update_snapshot(self) -> None:
        if psutil and self._process:
            mem_info = self._process.memory_info()
            self.snapshot.memory_mb = mem_info.rss // 1024 // 1024
        else:
            self.snapshot.memory_mb = 0
        self.snapshot.memory_percent = (
            self.snapshot.memory_mb * 100 // self.budget.memory_mb.limit
        )

        if psutil and self._process:
            cpu_percent = self._process.cpu_percent(interval=0)
        else:
            cpu_percent = 0.0
        self._cpu_history.append(cpu_percent)
        self.snapshot.cpu_percent = int(cpu_percent)
        self.snapshot.cpu_average_1m = int(sum(self._cpu_history) / len(self._cpu_history))

        if psutil:
            disk_usage = psutil.disk_usage(self.db_path)
            self.snapshot.disk_free_mb = disk_usage.free // 1024 // 1024
            self.snapshot.disk_used_mb = disk_usage.used // 1024 // 1024
        else:  # pragma: no cover - fallback
            self.snapshot.disk_free_mb = 0
            self.snapshot.disk_used_mb = 0

        now = self.time_service.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        self.snapshot.tokens_used_hour = sum(tokens for ts, tokens in self._token_history if ts > hour_ago)
        self.snapshot.tokens_used_day = sum(tokens for ts, tokens in self._token_history if ts > day_ago)
        self.snapshot.thoughts_active = self._count_active_thoughts()

    async def _check_limits(self) -> None:
        self.snapshot.warnings.clear()
        self.snapshot.critical.clear()
        self.snapshot.healthy = True
        await self._check_resource("memory_mb", self.snapshot.memory_mb)
        await self._check_resource("cpu_percent", self.snapshot.cpu_average_1m)
        await self._check_resource("tokens_hour", self.snapshot.tokens_used_hour)
        await self._check_resource("tokens_day", self.snapshot.tokens_used_day)
        await self._check_resource("thoughts_active", self.snapshot.thoughts_active)
        if self.snapshot.critical:
            self.snapshot.healthy = False

    async def _check_resource(self, name: str, current_value: int) -> None:
        limit_config: ResourceLimit = getattr(self.budget, name)
        if current_value >= limit_config.critical:
            self.snapshot.critical.append(f"{name}: {current_value}/{limit_config.limit}")
            await self._take_action(name, limit_config, "critical")
        elif current_value >= limit_config.warning:
            self.snapshot.warnings.append(f"{name}: {current_value}/{limit_config.limit}")
            await self._take_action(name, limit_config, "warning")

    async def _take_action(self, resource: str, config: ResourceLimit, level: str) -> None:
        last_action = self._last_action_time.get(f"{resource}_{level}")
        current_time = self.time_service.now()
        if last_action and current_time - last_action < timedelta(seconds=config.cooldown_seconds):
            return
        action = config.action
        logger.warning("Resource %s hit %s threshold, action: %s", resource, level, action)
        if action == ResourceAction.THROTTLE:
            await self.signal_bus.emit("throttle", resource)
        elif action == ResourceAction.DEFER:
            await self.signal_bus.emit("defer", resource)
        elif action == ResourceAction.REJECT:
            await self.signal_bus.emit("reject", resource)
        elif action == ResourceAction.SHUTDOWN:
            await self.signal_bus.emit("shutdown", resource)
        self._last_action_time[f"{resource}_{level}"] = current_time

    async def record_tokens(self, tokens: int) -> None:
        current_time = self.time_service.now()
        self._token_history.append((current_time, tokens))

    async def check_available(self, resource: str, amount: int = 0) -> bool:
        if resource == "memory_mb":
            return self.snapshot.memory_mb + amount < self.budget.memory_mb.warning
        if resource == "tokens_hour":
            return self.snapshot.tokens_used_hour + amount < self.budget.tokens_hour.warning
        if resource == "thoughts_active":
            return self.snapshot.thoughts_active + amount < self.budget.thoughts_active.warning
        return True

    def _count_active_thoughts(self) -> int:
        try:
            conn = get_db_connection(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM thoughts WHERE status IN ('pending', 'processing')"
            )
            row = cursor.fetchone()
            return row[0] if row else 0
        except Exception:  # pragma: no cover - DB errors unlikely in tests
            return 0

    def get_status(self) -> ServiceStatus:
        """Get service status as required by ServiceProtocol."""
        uptime = 0.0
        if self._start_time:
            uptime = (self.time_service.now() - self._start_time).total_seconds()
            
        return ServiceStatus(
            service_name="ResourceMonitorService",
            service_type="infrastructure_service",
            is_healthy=self.snapshot.healthy,
            uptime_seconds=uptime,
            metrics={
                "memory_mb": float(self.snapshot.memory_mb),
                "cpu_percent": float(self.snapshot.cpu_percent),
                "tokens_used_hour": float(self.snapshot.tokens_used_hour),
                "thoughts_active": float(self.snapshot.thoughts_active),
                "warnings": float(len(self.snapshot.warnings)),
                "critical": float(len(self.snapshot.critical))
            },
            last_error=None,
            last_health_check=self.time_service.now()
        )

    async def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self.snapshot.healthy

    def get_capabilities(self) -> ServiceCapabilities:
        """Get service capabilities as required by ServiceProtocol."""
        return ServiceCapabilities(
            service_name="ResourceMonitorService",
            actions=[
                "resource_monitoring",
                "cpu_tracking",
                "memory_tracking",
                "token_rate_limiting",
                "thought_counting",
                "resource_signals"
            ],
            version="1.0.0",
            dependencies=["TimeService"],
            metadata=None
        )
