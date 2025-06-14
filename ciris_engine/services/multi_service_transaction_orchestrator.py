"""Multi-Service Transaction Orchestrator."""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Any

from ciris_engine.adapters.base import Service
from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink
from ciris_engine.schemas.service_actions_v1 import ActionMessage
from ciris_engine.schemas.foundational_schemas_v1 import ServiceType

logger = logging.getLogger(__name__)


class MultiServiceTransactionOrchestrator(Service):
    """Orchestrate multi-service transactions via MultiServiceActionSink."""

    def __init__(self, service_registry: Any, action_sink: MultiServiceActionSink, app_config: Optional[Any] = None) -> None:
        super().__init__()
        self.registry = service_registry
        self.sink = action_sink
        self.app_config = app_config
        self.transactions: Dict[str, Dict[str, str]] = {}
        self._tasks: List[asyncio.Task] = []
        self._health_monitor_task: Optional[asyncio.Task] = None
        self._health_check_interval = 30.0  # Check every 30 seconds
        self._last_home_channel: Optional[str] = None

    async def start(self) -> None:
        await super().start()
        self._health_monitor_task = asyncio.create_task(self._health_monitor_loop())
        self._tasks.append(self._health_monitor_task)
        logger.info("Multi-Service Transaction Orchestrator started with health monitoring")

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

    async def get_status(self, tx_id: Optional[str] = None) -> Dict[str, Any]:
        """Get status of a specific transaction or overall service status."""
        if tx_id is not None:
            # Return specific transaction status
            tx_status = self.transactions.get(tx_id)
            if tx_status is not None:
                return tx_status
            else:
                return {"status": "not_found"}
        else:
            # Return overall service status
            return {
                "active_transactions": len(self.transactions),
                "service_type": "transaction_orchestrator",
                "transactions": dict(self.transactions)
            }
    
    def get_transaction_status(self, tx_id: str) -> Optional[Dict[str, str]]:
        """Get status of a specific transaction."""
        return self.transactions.get(tx_id)

    def get_service_health(self) -> Dict[str, Any]:
        """Get basic provider info from the registry."""
        if self.registry:
            provider_info = self.registry.get_provider_info()
            return provider_info if isinstance(provider_info, dict) else {}
        return {}

    async def _health_monitor_loop(self) -> None:
        """Continuous health monitoring loop that updates home channel."""
        logger.debug("Health monitor loop starting with 5 second delay for service registration")
        await asyncio.sleep(5.0)
        
        while True:
            try:
                await self._update_home_channel()
                await asyncio.sleep(self._health_check_interval)
            except asyncio.CancelledError:
                logger.info("Health monitor loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}", exc_info=True)
                await asyncio.sleep(self._health_check_interval)

    async def _update_home_channel(self) -> None:
        """Update app_config.home_channel based on highest priority healthy communication service."""
        if not self.registry or not self.app_config:
            return
        
        try:
            # Get the best available communication service
            communication_service = await self.registry.get_service(ServiceType.COMMUNICATION, "SpeakHandler")
            
            if not communication_service:
                # No communication services available - this is normal during startup
                if self._last_home_channel is not None:
                    logger.debug("No healthy communication services available - home channel may be stale")
                else:
                    logger.debug("No communication services registered yet - waiting for adapters to start")
                return
            
            # Try to get home channel from the service
            home_channel = None
            if hasattr(communication_service, 'get_home_channel_id'):
                try:
                    home_channel = communication_service.get_home_channel_id()
                except Exception as e:
                    logger.warning(f"Failed to get home channel from communication service: {e}")
            
            # Fallback: try to get channel from service config
            if not home_channel and hasattr(communication_service, 'config'):
                config = getattr(communication_service, 'config', None)
                if config and hasattr(config, 'get_home_channel_id'):
                    try:
                        home_channel = config.get_home_channel_id()
                    except Exception as e:
                        logger.warning(f"Failed to get home channel from service config: {e}")
            
            # Update app_config if we have a new home channel
            if home_channel and home_channel != self._last_home_channel:
                if hasattr(self.app_config, 'home_channel'):
                    self.app_config.home_channel = home_channel
                    self._last_home_channel = home_channel
                    logger.info(f"Updated home channel to: {home_channel}")
                else:
                    logger.warning("app_config does not have home_channel attribute")
                    
        except Exception as e:
            logger.error(f"Error updating home channel: {e}", exc_info=True)
