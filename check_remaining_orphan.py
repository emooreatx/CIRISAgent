from ciris_engine.logic.persistence.db.core import get_db_connection

with get_db_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT n.node_id, n.node_type, n.scope
        FROM graph_nodes n
        LEFT JOIN graph_edges e1 ON n.node_id = e1.source_node_id
        LEFT JOIN graph_edges e2 ON n.node_id = e2.target_node_id
        WHERE e1.edge_id IS NULL AND e2.edge_id IS NULL
          AND n.scope = 'local'
          AND n.node_type != 'tsdb_data'
          AND datetime(n.created_at) >= datetime('2025-07-13T12:00:00')
          AND datetime(n.created_at) < datetime('2025-07-13T18:00:00')
    """)
    
    for row in cursor:
        print(f"{row['node_id']} ({row['node_type']}, scope: {row['scope']})")