#!/usr/bin/env python3
"""Debug which nodes are missing from the period."""

import asyncio
from datetime import datetime, timezone
from ciris_engine.logic.services.graph.tsdb_consolidation.query_manager import QueryManager
from ciris_engine.logic.persistence.db.core import get_db_connection


async def check_missing_nodes():
    period_start = datetime(2025, 7, 13, 12, 0, 0, tzinfo=timezone.utc)
    period_end = datetime(2025, 7, 13, 18, 0, 0, tzinfo=timezone.utc)
    
    # Query all nodes in the period
    query_manager = QueryManager(memory_bus=None)
    nodes_by_type = await query_manager.query_all_nodes_in_period(period_start, period_end)
    
    all_node_ids = []
    for node_type, result in nodes_by_type.items():
        if hasattr(result, 'nodes'):
            for node in result.nodes:
                all_node_ids.append(node.id)
    
    print(f"Query found {len(all_node_ids)} nodes for the period")
    
    # Check which ones actually exist
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        missing = []
        for node_id in all_node_ids:
            cursor.execute("SELECT node_id FROM graph_nodes WHERE node_id = ?", (node_id,))
            if not cursor.fetchone():
                missing.append(node_id)
        
        print(f"\nMissing nodes: {len(missing)}")
        for node_id in missing[:10]:
            print(f"  - {node_id}")
        
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")


if __name__ == "__main__":
    asyncio.run(check_missing_nodes())