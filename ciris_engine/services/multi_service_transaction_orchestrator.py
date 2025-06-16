"""Multi-Service Transaction Orchestrator."""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Any

from ciris_engine.adapters.base import Service
from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink
from ciris_engine.schemas.service_actions_v1 import ActionMessage, ActionType, LogAuditEventAction
from ciris_engine.schemas.foundational_schemas_v1 import ServiceType
from ciris_engine.schemas.audit_schemas_v1 import AuditLogEntry

logger = logging.getLogger(__name__)


class MultiServiceTransactionOrchestrator(Service):
    """Orchestrate multi-service transactions via MultiServiceActionSink."""

    def __init__(self, service_registry: Any, action_sink: MultiServiceActionSink, app_config: Optional[Any] = None) -> None:
        super().__init__()
        self.registry = service_registry
        self.sink = action_sink
        self.app_config = app_config
        self.transactions: Dict[str, Dict[str, Any]] = {}
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
        """Execute a sequence of actions as a transaction, with special handling for broadcast actions."""
        self.transactions[tx_id] = {"status": "in_progress", "actions": str(len(actions))}
        
        for i, action in enumerate(actions):
            try:
                # Check if this is an audit event that needs broadcasting
                if action.type == ActionType.LOG_AUDIT_EVENT:
                    # Cast to LogAuditEventAction for broadcast
                    if isinstance(action, LogAuditEventAction):
                        await self._broadcast_audit_event(tx_id, action)
                    else:
                        logger.error("Expected LogAuditEventAction but got %s", type(action))
                        raise TypeError(f"Cannot broadcast non-audit action: {type(action)}")
                else:
                    # Normal single-service routing
                    await self.sink.enqueue_action(action)
                    
            except Exception as exc:  # noqa: BLE001
                logger.error("Transaction %s failed on action %d (%s): %s", tx_id, i, action.type, exc)
                self.transactions[tx_id] = {"status": "failed", "error": str(exc), "failed_at": str(i)}
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
            communication_service = await self.registry.get_service("SpeakHandler", ServiceType.COMMUNICATION)
            
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
    
    async def _broadcast_audit_event(self, tx_id: str, action: LogAuditEventAction) -> None:
        """Broadcast an audit event to ALL registered audit services."""
        if not self.registry:
            logger.error("No service registry available for audit broadcast")
            raise RuntimeError("Service registry required for audit broadcast")
        
        # Get ALL audit services (not just the best one)
        audit_services = self.registry.get_services_by_type('audit')
        
        if not audit_services:
            logger.error("No audit services available for broadcast")
            raise RuntimeError("No audit services registered")
        
        logger.info(f"Broadcasting audit event to {len(audit_services)} audit services")
        
        # Track broadcast results
        broadcast_results = {}
        failures = []
        
        # Send to all audit services in parallel
        tasks = []
        for i, service in enumerate(audit_services):
            service_id = f"{service.__class__.__name__}_{i}"
            task = asyncio.create_task(self._send_to_audit_service(service, action, service_id))
            tasks.append((service_id, task))
        
        # Wait for all to complete
        for service_id, task in tasks:
            try:
                result = await task
                broadcast_results[service_id] = result
                if not result:
                    failures.append(service_id)
            except Exception as e:
                logger.error(f"Audit broadcast failed for {service_id}: {e}")
                broadcast_results[service_id] = False
                failures.append(service_id)
        
        # Store broadcast results in transaction
        if tx_id in self.transactions:
            tx_data = self.transactions[tx_id]
            if isinstance(tx_data, dict):
                tx_data["audit_broadcast"] = {
                    "total_services": len(audit_services),
                    "results": broadcast_results,
                    "failures": failures
                }
        
        # If any critical services failed, consider the broadcast failed
        if failures:
            logger.warning(f"Audit broadcast partially failed: {len(failures)}/{len(audit_services)} services failed")
            # Don't throw exception - audit failures shouldn't break the transaction
    
    async def _send_to_audit_service(self, service: Any, action: LogAuditEventAction, service_id: str) -> bool:
        """Send audit event to a specific service."""
        try:
            await service.log_event(action.event_type, action.event_data)
            logger.debug(f"Successfully sent audit event to {service_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send audit event to {service_id}: {e}")
            return False
    
    async def broadcast_audit_event(self, event_type: str, event_data: Dict[str, Any]) -> str:
        """
        Convenience method to broadcast an audit event to all audit services.
        
        Returns:
            Transaction ID for tracking the broadcast
        """
        tx_id = f"audit_broadcast_{asyncio.get_event_loop().time()}"
        
        # Create the audit action
        audit_action = LogAuditEventAction(
            handler_name="TransactionOrchestrator",
            metadata={"broadcast": True},
            event_type=event_type,
            event_data=event_data
        )
        
        # Use orchestrate to handle the broadcast
        await self.orchestrate(tx_id, [audit_action])
        
        return tx_id
