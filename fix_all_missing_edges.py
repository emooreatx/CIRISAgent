#!/usr/bin/env python3
"""
Fix missing SUMMARIZES edges for all existing summaries.

This script retroactively creates edges for summaries that were created
before the edge creation logic was fixed.
"""

import asyncio
from datetime import datetime, timezone
from ciris_engine.logic.persistence.db.core import get_db_connection
from ciris_engine.logic.services.graph.tsdb_consolidation.service import TSDBConsolidationService
from ciris_engine.logic.services.graph.tsdb_consolidation.edge_manager import EdgeManager
from ciris_engine.logic.services.graph.tsdb_consolidation.query_manager import QueryManager
from ciris_engine.logic.services.graph.tsdb_consolidation.period_manager import PeriodManager


async def fix_all_missing_edges():
    """Fix missing edges for all summaries."""
    
    # First, find all summaries without edges
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Get all summaries and their edge counts
        cursor.execute("""
            SELECT 
                n.node_id,
                json_extract(n.attributes_json, '$.period_start') as period_start,
                json_extract(n.attributes_json, '$.period_end') as period_end,
                json_extract(n.attributes_json, '$.consolidation_level') as level,
                COALESCE(e.edge_count, 0) as edge_count
            FROM graph_nodes n
            LEFT JOIN (
                SELECT source_node_id, COUNT(*) as edge_count
                FROM graph_edges
                WHERE relationship = 'SUMMARIZES'
                GROUP BY source_node_id
            ) e ON n.node_id = e.source_node_id
            WHERE n.node_type = 'tsdb_summary'
            ORDER BY period_start
        """)
        
        summaries = cursor.fetchall()
        
    print(f"Found {len(summaries)} total summaries")
    
    # Count summaries needing fixes
    need_fix = [s for s in summaries if s['edge_count'] == 0]
    print(f"Found {len(need_fix)} summaries without edges")
    
    if not need_fix:
        print("All summaries have edges!")
        return
    
    # Create minimal components
    edge_manager = EdgeManager()
    query_manager = QueryManager(memory_bus=None)
    period_manager = PeriodManager()
    
    # Create a minimal TSDB service
    tsdb_service = TSDBConsolidationService.__new__(TSDBConsolidationService)
    tsdb_service._edge_manager = edge_manager
    tsdb_service._query_manager = query_manager
    tsdb_service._period_manager = period_manager
    tsdb_service._memory_bus = None
    
    # Fix each summary
    total_edges_created = 0
    
    for summary in need_fix:
        summary_id = summary['node_id']
        period_start = datetime.fromisoformat(summary['period_start'].replace('Z', '+00:00'))
        period_end = datetime.fromisoformat(summary['period_end'].replace('Z', '+00:00'))
        
        print(f"\nFixing {summary_id}:")
        print(f"  Period: {period_start} to {period_end}")
        
        # Count nodes in this period
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as node_count
                FROM graph_nodes
                WHERE scope = 'local'
                  AND node_type != 'tsdb_data'
                  AND datetime(created_at) >= datetime(?)
                  AND datetime(created_at) < datetime(?)
            """, (period_start.isoformat(), period_end.isoformat()))
            
            node_count = cursor.fetchone()['node_count']
            print(f"  Nodes in period: {node_count}")
        
        if node_count > 0:
            # Run the edge fix
            try:
                await tsdb_service._ensure_summary_edges(period_start, period_end)
                
                # Check how many edges were created
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT COUNT(*) as edge_count
                        FROM graph_edges
                        WHERE source_node_id = ?
                          AND relationship = 'SUMMARIZES'
                    """, (summary_id,))
                    
                    new_edge_count = cursor.fetchone()['edge_count']
                    print(f"  Created {new_edge_count} edges")
                    total_edges_created += new_edge_count
                    
            except Exception as e:
                print(f"  ERROR: {e}")
        else:
            print(f"  No nodes to link")
    
    print(f"\n✅ Fixed {len(need_fix)} summaries")
    print(f"✅ Created {total_edges_created} total edges")
    
    # Verify the fix
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Count remaining orphaned nodes
        cursor.execute("""
            WITH consolidated_periods AS (
                SELECT DISTINCT 
                    json_extract(attributes_json, '$.period_start') as period_start,
                    json_extract(attributes_json, '$.period_end') as period_end,
                    node_id as summary_id
                FROM graph_nodes 
                WHERE node_type = 'tsdb_summary'
            )
            SELECT COUNT(*) as orphaned_count
            FROM graph_nodes n
            INNER JOIN consolidated_periods p
                ON datetime(n.created_at) >= datetime(p.period_start)
                AND datetime(n.created_at) < datetime(p.period_end)
            WHERE n.scope = 'local'
                AND n.node_type != 'tsdb_data'
                AND NOT EXISTS (
                    SELECT 1 FROM graph_edges e
                    WHERE e.source_node_id = p.summary_id
                        AND e.target_node_id = n.node_id
                        AND e.relationship = 'SUMMARIZES'
                )
        """)
        
        remaining_orphans = cursor.fetchone()['orphaned_count']
        print(f"\n📊 Remaining orphaned nodes: {remaining_orphans}")


if __name__ == "__main__":
    print("TSDB Edge Fix Tool")
    print("==================")
    print("This will retroactively create SUMMARIZES edges for all summaries.")
    print()
    
    asyncio.run(fix_all_missing_edges())