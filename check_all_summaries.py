from ciris_engine.logic.persistence.db.core import get_db_connection
from datetime import datetime

# Check ALL summaries and their edge counts
with get_db_connection() as conn:
    cursor = conn.cursor()
    
    # Get all summaries
    cursor.execute("""
        SELECT 
            node_id,
            json_extract(attributes_json, '$.period_start') as period_start,
            json_extract(attributes_json, '$.period_end') as period_end,
            json_extract(attributes_json, '$.consolidation_level') as level
        FROM graph_nodes
        WHERE node_type = 'tsdb_summary'
        ORDER BY period_start DESC
        LIMIT 20
    """)
    
    summaries = cursor.fetchall()
    
    print(f"Checking {len(summaries)} summaries...\n")
    
    total_orphaned = 0
    
    for summary in summaries:
        summary_id = summary["node_id"]
        period_start = summary["period_start"]
        period_end = summary["period_end"]
        level = summary["level"] or "basic"
        
        # Count edges
        cursor.execute("""
            SELECT COUNT(*) as edge_count
            FROM graph_edges
            WHERE source_node_id = ?
              AND relationship = 'SUMMARIZES'
        """, (summary_id,))
        edge_count = cursor.fetchone()["edge_count"]
        
        # Count nodes in period
        cursor.execute("""
            SELECT COUNT(*) as node_count
            FROM graph_nodes
            WHERE scope = 'local'
              AND node_type != 'tsdb_data'
              AND datetime(created_at) >= datetime(?)
              AND datetime(created_at) < datetime(?)
        """, (period_start, period_end))
        node_count = cursor.fetchone()["node_count"]
        
        # Count orphaned nodes
        cursor.execute("""
            SELECT COUNT(*) as orphan_count
            FROM graph_nodes n
            WHERE n.scope = 'local'
              AND n.node_type != 'tsdb_data'
              AND datetime(n.created_at) >= datetime(?)
              AND datetime(n.created_at) < datetime(?)
              AND NOT EXISTS (
                  SELECT 1 FROM graph_edges e
                  WHERE e.source_node_id = ?
                    AND e.target_node_id = n.node_id
                    AND e.relationship = 'SUMMARIZES'
              )
        """, (period_start, period_end, summary_id))
        orphan_count = cursor.fetchone()["orphan_count"]
        
        total_orphaned += orphan_count
        
        # Parse dates for display
        try:
            start_dt = datetime.fromisoformat(period_start.replace('Z', '+00:00'))
            period_str = start_dt.strftime('%Y-%m-%d %H:%M')
        except (ValueError, TypeError):
            period_str = period_start[:16]
        
        print(f"{period_str} | {summary_id}")
        print(f"  Level: {level}")
        print(f"  Nodes in period: {node_count}")
        print(f"  SUMMARIZES edges: {edge_count}")
        print(f"  Orphaned nodes: {orphan_count}")
        
        if orphan_count > 0:
            print(f"  ⚠️  {orphan_count} nodes without edges!")
            # Show sample orphans
            cursor.execute("""
                SELECT n.node_id, n.node_type
                FROM graph_nodes n
                WHERE n.scope = 'local'
                  AND n.node_type != 'tsdb_data'
                  AND datetime(n.created_at) >= datetime(?)
                  AND datetime(n.created_at) < datetime(?)
                  AND NOT EXISTS (
                      SELECT 1 FROM graph_edges e
                      WHERE e.source_node_id = ?
                        AND e.target_node_id = n.node_id
                        AND e.relationship = 'SUMMARIZES'
                  )
                LIMIT 3
            """, (period_start, period_end, summary_id))
            for orphan in cursor:
                print(f"    - {orphan['node_id']} ({orphan['node_type']})")
        
        print()
    
    print(f"\nTotal orphaned nodes across all periods: {total_orphaned}")