"""Multi-Service Transaction Orchestrator."""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Any

from ciris_engine.adapters.base import Service
from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink
from ciris_engine.schemas.service_actions_v1 import ActionMessage

logger = logging.getLogger(__name__)


class MultiServiceTransactionOrchestrator(Service):
    """Orchestrate multi-service transactions via MultiServiceActionSink."""

    def __init__(self, service_registry: Any, action_sink: MultiServiceActionSink) -> None:
        super().__init__()
        self.registry = service_registry
        self.sink = action_sink
        self.transactions: Dict[str, Dict[str, str]] = {}
        self._tasks: List[asyncio.Task] = []

    async def start(self) -> None:
        await super().start()
        logger.info("Multi-Service Transaction Orchestrator started")

    async def stop(self) -> None:
        for task in list(self._tasks):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        await super().stop()
        logger.info("Multi-Service Transaction Orchestrator stopped")

    async def orchestrate(self, tx_id: str, actions: List[ActionMessage]) -> None:
        """Execute a sequence of actions as a transaction."""
        self.transactions[tx_id] = {"status": "in_progress"}
        for action in actions:
            try:
                await self.sink.enqueue_action(action)
            except Exception as exc:  # noqa: BLE001
                logger.error("Transaction %s failed on %s: %s", tx_id, action.type, exc)
                self.transactions[tx_id] = {"status": "failed", "error": str(exc)}
                await self.rollback(tx_id)
                return
        self.transactions[tx_id] = {"status": "complete"}

    async def rollback(self, tx_id: str) -> None:
        """Placeholder rollback logic."""
        logger.warning("Rolling back transaction %s", tx_id)

    async def get_status(self, tx_id: str) -> Optional[Dict[str, str]]:
        """Get status of a transaction."""
        return self.transactions.get(tx_id)

    def get_service_health(self) -> Dict[str, Any]:
        """Get basic provider info from the registry."""
        if self.registry:
            return self.registry.get_provider_info()
        return {}
