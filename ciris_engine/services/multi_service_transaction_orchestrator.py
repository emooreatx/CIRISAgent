"""Temporary stub for MultiServiceTransactionOrchestrator - to be migrated to BusManager"""

from ciris_engine.adapters.base import Service
from typing import Any, Optional

class MultiServiceTransactionOrchestrator(Service):
    """Temporary stub - functionality moved to BusManager"""
    
    def __init__(self, service_registry: Any, _action_sink: Any = None, app_config: Optional[Any] = None) -> None:
        super().__init__()
        self.registry = service_registry
        self.app_config = app_config
    
    async def start(self) -> None:
        await super().start()
    
    async def stop(self) -> None:
        await super().stop()
    
    async def broadcast_audit_event(self, event_type: str, event_data: dict) -> str:
        """Stub for audit broadcast - use BusManager.audit instead"""
        return "stub_tx_id"