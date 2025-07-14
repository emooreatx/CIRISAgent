#!/usr/bin/env python3
"""Debug script to test TSDB consolidation edge creation."""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

# Set up logging to see debug messages
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Import the necessary components
from ciris_engine.logic.services.graph.tsdb_consolidation import TSDBConsolidationService
from ciris_engine.logic.buses.memory_bus import MemoryBus
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol


class MockTimeService(TimeServiceProtocol):
    """Mock time service for testing."""
    def __init__(self):
        self._now = datetime.now(timezone.utc)
    
    def now(self) -> datetime:
        return self._now
    
    def now_iso(self) -> str:
        return self._now.isoformat()
    
    def timestamp(self) -> float:
        return self._now.timestamp()
    
    def get_uptime(self) -> float:
        return 0.0
    
    async def start(self) -> None:
        pass
    
    async def stop(self) -> None:
        pass
    
    async def is_healthy(self) -> bool:
        return True
    
    def get_service_type(self):
        from ciris_engine.schemas.runtime.enums import ServiceType
        return ServiceType.TIME
    
    def get_capabilities(self):
        from ciris_engine.schemas.services.core import ServiceCapabilities
        return ServiceCapabilities(
            service_name="MockTimeService",
            actions=["now"],
            version="1.0.0",
            dependencies=[],
            metadata={}
        )
    
    def get_status(self):
        from ciris_engine.schemas.services.core import ServiceStatus
        return ServiceStatus(
            service_name="MockTimeService",
            service_type="time",
            is_healthy=True,
            uptime_seconds=0.0,
            metrics={},
            last_error=None,
            last_health_check=self._now
        )


async def test_consolidation():
    """Test consolidation for a specific period."""
    print("=== TSDB Consolidation Debug Test ===\n")
    
    # Create a minimal service registry
    from ciris_engine.logic.infrastructure.service_registry import ServiceRegistry
    registry = ServiceRegistry()
    
    # Create services
    time_service = MockTimeService()
    memory_bus = MemoryBus(
        service_registry=registry,
        time_service=time_service
    )
    
    # Create consolidation service
    tsdb_service = TSDBConsolidationService(
        memory_bus=memory_bus,
        time_service=time_service
    )
    
    # Find a specific period to test - use the most recent one that should have been consolidated
    # Let's test 2025-07-13 12:00 to 18:00 which we know has issues
    period_start = datetime(2025, 7, 13, 12, 0, 0, tzinfo=timezone.utc)
    period_end = period_start + timedelta(hours=6)
    
    print(f"Testing consolidation for period: {period_start} to {period_end}")
    print("\nThis period already has a summary (tsdb_summary_20250713_12)")
    print("but nodes in this period have no edges.\n")
    
    # Manually run consolidation for this period
    print("Running _consolidate_period...")
    try:
        summaries = await tsdb_service._consolidate_period(period_start, period_end)
        print(f"\nConsolidation returned {len(summaries) if summaries else 0} summaries")
        
        if summaries:
            for summary in summaries:
                print(f"  - {summary.id} ({summary.type})")
    except Exception as e:
        print(f"\nError during consolidation: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== Test Complete ===")


if __name__ == "__main__":
    asyncio.run(test_consolidation())