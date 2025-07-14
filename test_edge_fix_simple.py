#!/usr/bin/env python3
"""Test the edge fix for consolidated periods - simplified version."""

import asyncio
import logging
from datetime import datetime, timezone

# Set up debug logging
logging.basicConfig(level=logging.INFO)

# Direct imports to avoid complex dependencies
from ciris_engine.logic.services.graph.tsdb_consolidation.service import TSDBConsolidationService
from ciris_engine.logic.services.graph.tsdb_consolidation.edge_manager import EdgeManager
from ciris_engine.logic.services.graph.tsdb_consolidation.query_manager import QueryManager
from ciris_engine.logic.services.graph.tsdb_consolidation.period_manager import PeriodManager
from ciris_engine.logic.persistence.db.core import get_db_connection


async def test_edge_fix():
    print("=== Testing Edge Fix for Consolidated Periods ===\n")
    
    # Create minimal components
    edge_manager = EdgeManager()
    query_manager = QueryManager(memory_bus=None)
    period_manager = PeriodManager()
    
    # Create a minimal TSDB service
    tsdb_service = TSDBConsolidationService.__new__(TSDBConsolidationService)
    tsdb_service._edge_manager = edge_manager
    tsdb_service._query_manager = query_manager
    tsdb_service._period_manager = period_manager
    tsdb_service._memory_bus = None  # We don't need memory bus for this test
    
    # Test period that has a summary but no edges
    period_start = datetime(2025, 7, 13, 12, 0, 0, tzinfo=timezone.utc)
    period_end = datetime(2025, 7, 13, 18, 0, 0, tzinfo=timezone.utc)
    
    print(f"Testing period: {period_start} to {period_end}")
    print("This period has summary tsdb_summary_20250713_12 but no SUMMARIZES edges\n")
    
    # Check edges before
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM graph_edges
            WHERE source_node_id = 'tsdb_summary_20250713_12'
              AND relationship = 'SUMMARIZES'
        """)
        
        before_count = cursor.fetchone()['count']
        print(f"SUMMARIZES edges before fix: {before_count}")
    
    # Call the edge fix method
    print("\nCalling _ensure_summary_edges...")
    await tsdb_service._ensure_summary_edges(period_start, period_end)
    
    # Check edges after
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM graph_edges
            WHERE source_node_id = 'tsdb_summary_20250713_12'
              AND relationship = 'SUMMARIZES'
        """)
        
        after_count = cursor.fetchone()['count']
        print(f"\nSUMMARIZES edges after fix: {after_count}")
        
        if after_count > before_count:
            print(f"✅ SUCCESS! Created {after_count - before_count} new edges")
        else:
            print("❌ No new edges created")
    
    print("\n=== Test Complete ===")


if __name__ == "__main__":
    asyncio.run(test_edge_fix())