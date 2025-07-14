from ciris_engine.logic.persistence.db.core import get_db_connection

# Check actual SUMMARIZES edges
with get_db_connection() as conn:
    cursor = conn.cursor()
    
    # Count all SUMMARIZES edges
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM graph_edges
        WHERE relationship = 'SUMMARIZES'
    """)
    print(f'Total SUMMARIZES edges: {cursor.fetchone()["count"]}')
    
    # Check a specific summary
    cursor.execute("""
        SELECT COUNT(*) as edge_count
        FROM graph_edges
        WHERE source_node_id = 'tsdb_summary_20250713_18'
          AND relationship = 'SUMMARIZES'
    """)
    print(f'\nEdges from tsdb_summary_20250713_18: {cursor.fetchone()["edge_count"]}')
    
    # Check for orphaned nodes in that period
    cursor.execute("""
        SELECT COUNT(*) as orphan_count
        FROM graph_nodes n
        WHERE n.scope = 'local'
          AND n.node_type != 'tsdb_data'
          AND datetime(n.created_at) >= datetime('2025-07-13T18:00:00')
          AND datetime(n.created_at) < datetime('2025-07-14T00:00:00')
          AND NOT EXISTS (
              SELECT 1 FROM graph_edges e
              WHERE e.source_node_id = 'tsdb_summary_20250713_18'
                AND e.target_node_id = n.node_id
                AND e.relationship = 'SUMMARIZES'
          )
    """)
    print(f'\nOrphaned nodes in that period: {cursor.fetchone()["orphan_count"]}')
    
    # List some of those orphaned nodes
    cursor.execute("""
        SELECT n.node_id, n.node_type, n.created_at
        FROM graph_nodes n
        WHERE n.scope = 'local'
          AND n.node_type != 'tsdb_data'
          AND datetime(n.created_at) >= datetime('2025-07-13T18:00:00')
          AND datetime(n.created_at) < datetime('2025-07-14T00:00:00')
          AND NOT EXISTS (
              SELECT 1 FROM graph_edges e
              WHERE e.source_node_id = 'tsdb_summary_20250713_18'
                AND e.target_node_id = n.node_id
                AND e.relationship = 'SUMMARIZES'
          )
        LIMIT 10
    """)
    print('\nSample orphaned nodes:')
    for row in cursor:
        print(f'  - {row["node_id"]} ({row["node_type"]}) created at {row["created_at"]}')
    
    # Check what edges DO exist for this summary
    cursor.execute("""
        SELECT DISTINCT e.target_node_id, n.node_type
        FROM graph_edges e
        JOIN graph_nodes n ON e.target_node_id = n.node_id
        WHERE e.source_node_id = 'tsdb_summary_20250713_18'
          AND e.relationship = 'SUMMARIZES'
        LIMIT 10
    """)
    print('\nSample edges that DO exist:')
    for row in cursor:
        print(f'  - {row["target_node_id"]} ({row["node_type"]})')