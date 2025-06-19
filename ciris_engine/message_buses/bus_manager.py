"""
BusManager - Orchestrates all message buses
"""

import logging
from typing import Dict, Any, Optional

from ciris_engine.registries.base import ServiceRegistry
from .communication_bus import CommunicationBus
from .memory_bus import MemoryBus
from .tool_bus import ToolBus
from .audit_bus import AuditBus
from .telemetry_bus import TelemetryBus
from .wise_bus import WiseBus
from .llm_bus import LLMBus

logger = logging.getLogger(__name__)


class BusManager:
    """
    Central manager for all message buses.
    
    This replaces the MultiServiceTransactionOrchestrator with a cleaner,
    typed interface. Each bus handles one service type.
    
    Handlers access buses through this manager:
    - bus_manager.communication.send_message(...)
    - bus_manager.memory.memorize(...)
    - etc.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        
        # Initialize all buses
        self.communication = CommunicationBus(service_registry)
        self.memory = MemoryBus(service_registry)
        self.tool = ToolBus(service_registry)
        self.audit = AuditBus(service_registry)
        self.telemetry = TelemetryBus(service_registry)
        self.wise = WiseBus(service_registry)
        # LLM bus needs telemetry bus for resource tracking
        self.llm = LLMBus(service_registry, telemetry_bus=self.telemetry)
        
        # Store all buses for lifecycle management
        self._buses = {
            "communication": self.communication,
            "memory": self.memory,
            "tool": self.tool,
            "audit": self.audit,
            "telemetry": self.telemetry,
            "wise": self.wise,
            "llm": self.llm
        }
        
        logger.info("BusManager initialized with all message buses")
    
    async def start(self) -> None:
        """Start all message buses"""
        logger.info("Starting all message buses...")
        for name, bus in self._buses.items():
            try:
                await bus.start()
                logger.info(f"Started {name} bus")
            except Exception as e:
                logger.error(f"Failed to start {name} bus: {e}", exc_info=True)
                # Continue starting other buses
        logger.info("All message buses started")
    
    async def stop(self) -> None:
        """Stop all message buses"""
        logger.info("Stopping all message buses...")
        for name, bus in self._buses.items():
            try:
                await bus.stop()
                logger.info(f"Stopped {name} bus")
            except Exception as e:
                logger.error(f"Failed to stop {name} bus: {e}", exc_info=True)
                # Continue stopping other buses
        logger.info("All message buses stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics from all buses"""
        stats = {}
        for name, bus in self._buses.items():
            stats[name] = bus.get_stats()
        return stats
    
    def get_total_queue_size(self) -> int:
        """Get total messages queued across all buses"""
        return sum(bus.get_queue_size() for bus in self._buses.values())
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all buses"""
        health = {}
        for name, bus in self._buses.items():
            # A bus is healthy if it's running and queue isn't full
            is_running = getattr(bus, '_running', False)
            queue_healthy = bus.get_queue_size() < bus.max_queue_size * 0.9
            health[name] = is_running and queue_healthy
        return health