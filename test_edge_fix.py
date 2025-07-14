#!/usr/bin/env python3
"""Test the edge fix for consolidated periods."""

import asyncio
from datetime import datetime, timezone

# Import services
from ciris_engine.logic.services.graph.tsdb_consolidation import TSDBConsolidationService
from ciris_engine.logic.buses.memory_bus import MemoryBus
from ciris_engine.logic.runtime.service_registry import ServiceRegistry
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol


class MockTimeService(TimeServiceProtocol):
    """Mock time service."""
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


async def test_edge_fix():
    print("=== Testing Edge Fix for Consolidated Periods ===\n")
    
    # Create services
    registry = ServiceRegistry()
    time_service = MockTimeService()
    memory_bus = MemoryBus(service_registry=registry, time_service=time_service)
    
    # Create consolidation service
    tsdb_service = TSDBConsolidationService(
        memory_bus=memory_bus,
        time_service=time_service
    )
    
    # Test period that has a summary but no edges
    period_start = datetime(2025, 7, 13, 12, 0, 0, tzinfo=timezone.utc)
    period_end = datetime(2025, 7, 13, 18, 0, 0, tzinfo=timezone.utc)
    
    print(f"Testing period: {period_start} to {period_end}")
    print("This period has summary tsdb_summary_20250713_12 but no SUMMARIZES edges\n")
    
    # Call the edge fix method
    print("Calling _ensure_summary_edges...")
    await tsdb_service._ensure_summary_edges(period_start, period_end)
    
    print("\n=== Test Complete ===")
    
    # Check if edges were created
    from ciris_engine.logic.persistence.db.core import get_db_connection
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM graph_edges
            WHERE source_node_id = 'tsdb_summary_20250713_12'
              AND relationship = 'SUMMARIZES'
        """)
        
        edge_count = cursor.fetchone()['count']
        print(f"\nSUMMARIZES edges after fix: {edge_count}")


if __name__ == "__main__":
    asyncio.run(test_edge_fix())