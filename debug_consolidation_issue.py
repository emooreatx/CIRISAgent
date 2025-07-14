#!/usr/bin/env python3
"""Debug why SUMMARIZES edges are not being created."""

import asyncio
from datetime import datetime, timezone
from ciris_engine.logic.persistence.db.core import get_db_connection
from ciris_engine.logic.services.graph.tsdb_consolidation.query_manager import QueryManager


async def investigate():
    # Test period that we know is consolidated
    period_start = datetime(2025, 7, 13, 12, 0, 0, tzinfo=timezone.utc)
    period_end = datetime(2025, 7, 13, 18, 0, 0, tzinfo=timezone.utc)
    
    print(f"Investigating period: {period_start} to {period_end}")
    print(f"Summary node: tsdb_summary_20250713_12\n")
    
    # Create query manager
    query_manager = QueryManager(memory_bus=None)
    
    # Query all nodes in the period
    print("1. Querying all nodes in the period...")
    nodes_by_type = await query_manager.query_all_nodes_in_period(period_start, period_end)
    
    print(f"\nFound node types: {list(nodes_by_type.keys())}")
    for node_type, result in nodes_by_type.items():
        if hasattr(result, 'nodes'):
            print(f"  {node_type}: {len(result.nodes)} nodes")
            # Show sample nodes
            for node in result.nodes[:2]:
                print(f"    - {node.id} (created: {node.updated_at})")
        else:
            print(f"  {node_type}: No nodes attribute!")
    
    # Check what edges exist from the summary
    print("\n2. Checking edges from tsdb_summary_20250713_12...")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Count edges by relationship
        cursor.execute("""
            SELECT relationship, COUNT(*) as count
            FROM graph_edges
            WHERE source_node_id = 'tsdb_summary_20250713_12'
            GROUP BY relationship
            ORDER BY count DESC
        """)
        
        edges_by_rel = cursor.fetchall()
        if edges_by_rel:
            print("Edges from summary:")
            for row in edges_by_rel:
                print(f"  {row['relationship']}: {row['count']}")
        else:
            print("NO EDGES from this summary!")
        
        # Check if there are any nodes created in this period
        print("\n3. Checking nodes created in the period...")
        cursor.execute("""
            SELECT node_type, COUNT(*) as count
            FROM graph_nodes
            WHERE datetime(created_at) >= datetime(?)
              AND datetime(created_at) < datetime(?)
              AND scope = 'local'
              AND node_type != 'tsdb_data'
            GROUP BY node_type
            ORDER BY count DESC
        """, (period_start.isoformat(), period_end.isoformat()))
        
        nodes_in_period = cursor.fetchall()
        total_nodes = sum(row['count'] for row in nodes_in_period)
        print(f"\nTotal nodes created in period: {total_nodes}")
        for row in nodes_in_period:
            print(f"  {row['node_type']}: {row['count']}")
        
        # Show some specific nodes
        cursor.execute("""
            SELECT node_id, node_type, created_at
            FROM graph_nodes
            WHERE datetime(created_at) >= datetime(?)
              AND datetime(created_at) < datetime(?)
              AND scope = 'local'
              AND node_type != 'tsdb_data'
            LIMIT 5
        """, (period_start.isoformat(), period_end.isoformat()))
        
        print("\nSample nodes from this period:")
        for row in cursor:
            print(f"  {row['node_id']} ({row['node_type']}) - {row['created_at']}")
    
    print("\n4. Checking if summary node exists...")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT node_id, created_at, updated_at
            FROM graph_nodes
            WHERE node_id = 'tsdb_summary_20250713_12'
        """)
        
        summary = cursor.fetchone()
        if summary:
            print(f"Summary exists: created {summary['created_at']}, updated {summary['updated_at']}")
        else:
            print("Summary node does NOT exist!")


if __name__ == "__main__":
    asyncio.run(investigate())